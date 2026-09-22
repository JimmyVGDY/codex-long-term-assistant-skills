#!/usr/bin/env python3
"""中文：V7 安装、验证与卸载器：支持官方账户 Skill 目录、Plugin-first、standalone 兼容、仓库级隔离、路径安全、事务恢复、受管旧 Skill 迁移、漂移检测与 dry-run；不自动删除未知资产。

English: V7 installer, verifier, and uninstaller for the standard account Skill directory, Plugin-first and standalone compatibility, repository isolation, path safety, transaction recovery, managed legacy-Skill migration, drift detection, and dry-run. It never automatically removes unknown assets.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

MINIMUM_PYTHON = (3, 11)
if sys.version_info < MINIMUM_PYTHON:
    print("[ERROR] Python 3.11+ required; actual=%s executable=%s" %
          (".".join(str(part) for part in sys.version_info[:3]), sys.executable), file=sys.stderr)
    raise SystemExit(2)

from codex_compatibility import (CompatibilityError, canonical_digest,
                                 load_registry, normalize_plugin_list,
                                 parse_codex_version_output, profile_for_version)
from payload_integrity import (MANIFEST_NAME as PAYLOAD_MANIFEST_NAME,
                               PayloadIntegrityError, load_manifest as load_payload_manifest,
                               verify_payload)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.integrity import init_keyring, verify_keyring  # noqa: E402
MANIFEST_PATH = ROOT / "manifest.json"
PACKAGE = "codex-cross-project-engineering-assistant"


def release_version() -> str:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        version = str(value["version"])
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        raise RuntimeError("manifest.json version unavailable") from None
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise RuntimeError("manifest.json version invalid")
    return version


VERSION = release_version()
MARKETPLACE = "cp-assistant-local"
BASE_MARKETPLACE = "cp-assistant-base"
BASE_STATE_FILE = "cp-assistant-base-state.json"
COMPATIBILITY_REGISTRY_PATH = ROOT / "config" / "codex-compatibility-v1.json"
COMPATIBILITY_REGISTRY = load_registry(COMPATIBILITY_REGISTRY_PATH, VERSION)
TARGET_CODEX_VERSION = str(COMPATIBILITY_REGISTRY["window_policy"]["anchor"])
# 中文：当前包按冻结的稳定发行序列支持当前版和前十个稳定发行版。
# English: The current package supports the frozen current stable release and ten preceding stable releases.
SUPPORTED_CODEX_VERSIONS = tuple(item["version"] for item in COMPATIBILITY_REGISTRY["versions"])
REPAIRABLE_MARKETPLACE_STATE_VERSIONS = frozenset({
    "6.1.0", "6.2.0", "6.3.0", "7.2.0", "7.3.0", "7.4.0",
    "7.6.0", "7.6.1", "7.6.2", "7.7.0", "7.7.1", "7.8.0", "7.8.1",
})
AUTO_MIGRATION_SOURCES = frozenset({
    "7.6.0", "7.6.1", "7.6.2", "7.7.0", "7.7.1", "7.8.0", "7.8.1",
})
SKILL_DIR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
BEGIN = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:BEGIN -->"
END = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:END -->"

class InstallError(RuntimeError):
    pass


JOURNAL_SCHEMA = 1
JOURNAL_STAGES = {"PREPARED", "BACKED_UP", "APPLYING", "ACTIVATING", "COMMITTED",
                  "ROLLBACK_STARTED", "ROLLED_BACK", "RECOVERY_REQUIRED"}


def _hard_crash(point: str) -> None:
    """中文：仅供测试的真实进程终止点，缺少显式环境变量时绝不启用。

    English: Test-only true process termination, never enabled without an explicit environment variable.
    """
    if os.environ.get("CP_ASSISTANT_TEST_HARD_CRASH_POINT") == point:
        os._exit(91)


def transaction_path(scope: str, repo: Optional[Path] = None) -> Path:
    """中文：每个作用域只有一份持久事务日志，并刻意放在备份目录之外。

    English: Keep one durable transaction journal per scope, deliberately outside backup directories.
    """
    return state_path(scope, repo).with_name("cp-assistant-v6-transaction.json")


@contextlib.contextmanager
def scope_lock(scope: str, repo: Optional[Path] = None) -> Iterable[None]:
    """中文：串行化账户或仓库作用域内的所有变更操作。

    English: Serialize every mutating operation within an account or repository scope.
    """
    lock = transaction_path(scope, repo).with_name("cp-assistant-v6.lock")
    reject_link_ancestors(lock.parent, repo if scope == "repo" else None)
    _io_path(lock.parent).mkdir(parents=True, exist_ok=True)
    handle = _io_path(lock).open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise InstallError("另一个安装/卸载事务正在此 scope 执行") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise InstallError("另一个安装/卸载事务正在此 scope 执行") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "scope": scope, "started_at": time.time(),
                                 "transaction": str(transaction_path(scope, repo))}).encode("utf-8"))
        handle.flush()
        yield
    finally:
        try:
            if os.name == "nt":
                # 中文：关闭 CRT 描述符会释放字节范围锁；Windows 缓冲可能改变当前位置，
                # 中文：因此在 Python 缓冲文件处理后调用 LK_UNLCK 并不可靠。
                # English: Closing the CRT descriptor releases its byte-range lock;
                # English: LK_UNLCK is unreliable after Python buffering changes the current byte.
                pass
            else:
                import fcntl; fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _journal_write(journal: Dict[str, Any], stage: str) -> None:
    if stage not in JOURNAL_STAGES:
        raise InstallError("未知事务阶段: %s" % stage)
    journal["stage"] = stage
    journal["updated_at"] = time.time()
    write_json_atomic(Path(journal["journal_path"]), journal)
    fault = os.environ.get("CP_ASSISTANT_TEST_FAIL_STAGE")
    if fault == stage:
        raise InstallError("测试故障注入: %s" % stage)
    if os.environ.get("CP_ASSISTANT_TEST_CRASH_STAGE") == stage:
        # 中文：受控异常会保留持久化事务日志，供 `doctor --recover` 恢复。
        # English: A controlled exception keeps the durable journal for `doctor --recover`.
        journal["crash_injected"] = True
        write_json_atomic(Path(journal["journal_path"]), journal)
        raise InstallError("测试崩溃注入: %s；请执行 doctor --recover" % stage)
    _hard_crash("STAGE:" + stage)


def _recheck_target(path: Path, scope: str, repo: Optional[Path] = None) -> None:
    if scope == "repo":
        assert repo is not None; ensure_inside(path, repo)
    reject_link_ancestors(path.parent, repo if scope == "repo" else None)
    if _is_reparse(path):
        raise InstallError("破坏性 I/O 前检测到链接型目标: %s" % path)


def _new_journal(scope: str, mode: str, repo: Optional[Path], targets: List[Tuple[str, Path]]) -> Dict[str, Any]:
    path = transaction_path(scope, repo)
    return {"schema_version": JOURNAL_SCHEMA, "transaction_id": str(uuid.uuid4()), "scope": scope,
            "mode": mode, "version": VERSION, "repo": str(repo) if repo else None,
            "backup": None, "targets": [{"label": label, "target": str(target)} for label, target in targets],
            "records": [], "applied_hashes": {}, "previous_plugin_state": {}, "errors": [],
            "rollback_errors": [], "journal_path": str(path), "stage": "PREPARED", "created_at": time.time()}


def _archive_final_journal(journal: Dict[str, Any]) -> None:
    backup = journal.get("backup")
    if backup:
        write_json_atomic(Path(backup) / "final-transaction.json", journal)


def _finish_journal(journal: Dict[str, Any]) -> None:
    """中文：归档终态事务并移除活动恢复标记。

    English: Archive a terminal transaction and remove its live recovery marker.
    """
    _archive_final_journal(journal)
    _io_path(Path(journal["journal_path"])).unlink(missing_ok=True)


def _require_no_live_transaction(scope: str, repo: Optional[Path] = None) -> None:
    live = _load_live_journal(scope, repo)
    if not live:
        return
    if live["stage"] in {"COMMITTED", "ROLLED_BACK"}:
        _finish_journal(live)
        return
    raise InstallError("存在未完成事务 %s（stage=%s）；请先执行 doctor --recover" %
                       (live.get("transaction_id"), live.get("stage")))


def _target_owned(record: Mapping[str, Any], journal: Mapping[str, Any]) -> bool:
    """中文：事务完成后若目标被外部修改，不删除该目标。

    English: Do not delete a target changed externally after this transaction.
    """
    label = str(record.get("label") or "")
    if label in {"global", "hooks-json"}:
        # 中文：恢复采用合并方式，并保留外部修改。
        # English: Restoration is merge-based and preserves external edits.
        return True
    target = Path(str(record["target"]))
    if not _io_path(target).exists():
        return True
    current = tree_sha256(target)
    expected = (journal.get("applied_hashes") or {}).get(str(target))
    if expected and current == expected:
        return True
    # 中文：已持久化的变更意图可能早于原子替换；未改动的事务前目录仍由本事务所有，
    # 中文：可以安全地进行幂等恢复。
    # English: A persisted mutation intent may precede the atomic swap; the untouched
    # English: pre-transaction tree is still owned and safe to restore idempotently.
    return bool(record.get("existed") and record.get("sha256") and current == record.get("sha256"))


def _record_applied(journal: Dict[str, Any], label: str, target: Path) -> None:
    """中文：每次破坏性目标动作后立即持久化所有权。

    English: Persist ownership immediately after each destructive target action.
    """
    journal.setdefault("applied_targets", {})[label] = {
        "target": str(target), "sha256": tree_sha256(target) if _io_path(target).exists() else "missing"}
    journal.setdefault("applied_hashes", {})[str(target)] = journal["applied_targets"][label]["sha256"]
    _journal_write(journal, str(journal["stage"]))
    if os.environ.get("CP_ASSISTANT_TEST_CRASH_AFTER_TARGET") == label:
        journal["crash_injected"] = True
        write_json_atomic(Path(journal["journal_path"]), journal)
        raise InstallError("测试目标动作崩溃注入: %s；请执行 doctor --recover" % label)
    _hard_crash("TARGET:" + label)


def _record_mutation_intent(journal: Dict[str, Any], label: str, target: Path, expected_hash: str) -> None:
    """中文：在原子替换目标前持久化唯一完整的变更后哈希。

    English: Persist the only complete post-mutation hash before an atomic target replacement.
    """
    journal.setdefault("pending_targets", {})[label] = {"target": str(target), "sha256": expected_hash}
    journal.setdefault("applied_hashes", {})[str(target)] = expected_hash
    _journal_write(journal, str(journal["stage"]))


def _user_mutation(func: Any) -> Any:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with scope_lock("user"):
            return func(*args, **kwargs)
    return wrapped


def _repo_mutation(func: Any) -> Any:
    def wrapped(repo_path: str, *args: Any, **kwargs: Any) -> Any:
        repo = git_root(Path(repo_path))
        with scope_lock("repo", repo):
            return func(str(repo), *args, **kwargs)
    return wrapped


def _io_path(path: Path) -> Path:
    """中文：返回用于文件系统 I/O 的 Windows 扩展长度路径；逻辑路径和清单保持可读，只在 I/O 边界添加 Win32 前缀。

    English: Return a Windows extended-length path for filesystem I/O. Keep logical paths and manifests readable and add the Win32 prefix only at I/O boundaries.
    """
    absolute = str(path.absolute())
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def load_json(path: Path, default: Any = None) -> Any:
    io_path = _io_path(path)
    if not io_path.exists():
        return default
    return json.loads(io_path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, value: Any) -> None:
    io_parent = _io_path(path.parent)
    io_parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(io_parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, _io_path(path))
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def text_atomic(path: Path, text: str) -> None:
    io_parent = _io_path(path.parent)
    io_parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(io_parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, _io_path(path))
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with _io_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(path: Path) -> str:
    io_root = _io_path(path)
    reject_tree_links(path)
    if io_root.is_file():
        return sha256_file(io_root)
    if not io_root.exists():
        return "missing"
    h = hashlib.sha256()
    for item in sorted((p for p in io_root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel = item.relative_to(io_root).as_posix()
        h.update(rel.encode("utf-8")); h.update(b"\0")
        h.update(sha256_file(item).encode("ascii")); h.update(b"\n")
    return h.hexdigest()


def _normalize_host_path(raw: str) -> Path:
    value = str(raw).strip()
    if os.name == "nt":
        # 中文：即使安装器由 Windows 原生 Python 执行，部分 Desktop/WSL 桥接会话仍可能继承
        # 中文：`/mnt/c/...`；必须先转换，再做所有权与重解析点检查，避免创建字面 `\\mnt\\c` 目录。
        # English: Some Desktop/WSL bridge sessions inherit `/mnt/c/...` under native Windows
        # English: Python; convert it before ownership/reparse checks to avoid a literal `\\mnt\\c` tree.
        m = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", value.replace("\\", "/"))
        if m:
            drive = m.group(1).upper()
            rest = (m.group(2) or "").replace("/", "\\")
            value = drive + ":\\" + rest if rest else drive + ":\\"
    return Path(value).expanduser().absolute()


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return _normalize_host_path(raw) if raw else (Path.home() / ".codex").expanduser().absolute()


def user_skills_home() -> Path:
    # 中文：Codex 当前账户级 Skills 规范目录不随 CODEX_HOME 改写。
    # English: The account-level Skills directory is independent of CODEX_HOME.
    return (Path.home() / ".agents" / "skills").expanduser().absolute()


def _is_reparse(path: Path) -> bool:
    try:
        st = _io_path(path).lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise InstallError("无法安全读取路径属性: %s" % path) from exc
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attrs & flag)


def reject_link_ancestors(path: Path, stop: Optional[Path] = None) -> None:
    current = path.absolute()
    stop_abs = stop.absolute() if stop else None
    chain: List[Path] = []
    while True:
        chain.append(current)
        if stop_abs is not None and current == stop_abs:
            break
        if current.parent == current:
            break
        current = current.parent
    for item in reversed(chain):
        if _is_reparse(item):
            raise InstallError("安全路径中不允许符号链接/Junction/Reparse Point: %s" % item)


def reject_tree_links(path: Path) -> None:
    """中文：不跟随链接，拒绝树内任何符号链接或 Reparse Point。

    English: Reject every link or reparse descendant without following it.
    """
    io_root = _io_path(path)
    if not io_root.exists() and not io_root.is_symlink():
        return
    if _is_reparse(io_root):
        raise InstallError("受管树不允许符号链接/Junction/Reparse Point: %s" % path)
    if not io_root.is_dir():
        return
    for base, directories, files in os.walk(str(io_root), topdown=True, followlinks=False):
        for name in list(directories) + list(files):
            candidate = Path(base) / name
            if _is_reparse(candidate):
                raise InstallError("受管树内部不允许符号链接/Junction/Reparse Point: %s" % candidate)


def _containment_path(path: Path) -> Path:
    """中文：规范化 Windows 设备前缀、短路径和大小写后再做词法包含判断。

    English: Normalize Windows device prefixes, short paths, and case before lexical containment checks.
    """
    value = str(path.absolute())
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        value = os.path.realpath(value)
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        value = os.path.normcase(os.path.normpath(value))
    return Path(value)


def ensure_inside(path: Path, root: Path) -> None:
    p = _containment_path(path)
    r = _containment_path(root)
    try:
        p.relative_to(r)
    except ValueError as exc:
        raise InstallError("目标路径越过受管根目录: %s" % path) from exc


def path_inside(path: Path, root: Path) -> bool:
    try:
        _containment_path(path).relative_to(_containment_path(root))
        return True
    except ValueError:
        return False


def git_root(repo: Path) -> Path:
    repo = repo.expanduser().absolute()
    reject_link_ancestors(repo)
    import subprocess
    try:
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], text=True, encoding="utf-8", errors="replace", capture_output=True, check=True, timeout=10)
    except Exception as exc:
        raise InstallError("repo-path 必须位于可识别的 Git 仓库中") from exc
    root = Path(result.stdout.strip()).absolute()
    reject_link_ancestors(root)
    return root


def remove_path(path: Path) -> None:
    io_path = _io_path(path)
    if io_path.is_symlink():
        io_path.unlink()
    elif io_path.is_dir():
        reject_tree_links(path)
        shutil.rmtree(io_path)
    elif io_path.exists():
        io_path.unlink()


def copy_atomic(src: Path, dst: Path) -> None:
    reject_link_ancestors(dst.parent)
    _io_path(dst.parent).mkdir(parents=True, exist_ok=True)
    reject_link_ancestors(dst.parent)
    # 中文：暂存目录名刻意保持简短；重复较长的 Plugin 名和 `payload` 组件可能越过旧版
    # 中文：Windows MAX_PATH 限制，即使最终目标路径本身有效。
    # English: Keep the staging component short; repeating a long Plugin name and `payload`
    # English: can exceed legacy Windows MAX_PATH even when the final destination is valid.
    tmp = Path(tempfile.mkdtemp(prefix=".cp-", dir=str(_io_path(dst.parent))))
    try:
        io_src = _io_path(src)
        reject_tree_links(src)
        io_tmp = _io_path(tmp)
        if io_src.is_dir():
            shutil.copytree(io_src, io_tmp, symlinks=False, dirs_exist_ok=True)
            staged = tmp
        else:
            staged = tmp / "f"
            _io_path(staged.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(io_src, _io_path(staged))
        io_dst = _io_path(dst)
        if io_dst.exists() or io_dst.is_symlink():
            reject_tree_links(dst)
            remove_path(dst)
        os.replace(str(_io_path(staged)), str(io_dst))
    finally:
        shutil.rmtree(_io_path(tmp), ignore_errors=True)


def backup_target(path: Path, backup_root: Path, label: str) -> Dict[str, Any]:
    io_path = _io_path(path)
    record: Dict[str, Any] = {"target": str(path), "label": label, "existed": bool(io_path.exists() or io_path.is_symlink())}
    if not record["existed"]:
        return record
    if _is_reparse(path):
        raise InstallError("拒绝备份并覆盖链接型目标: %s" % path)
    reject_tree_links(path)
    items_root = _io_path(backup_root / "items")
    rel = "items/%03d-%s" % (len(list(items_root.glob("*"))) if items_root.exists() else 0, re.sub(r"[^A-Za-z0-9._-]+", "-", label)[:60])
    out = backup_root / rel
    _io_path(out.parent).mkdir(parents=True, exist_ok=True)
    if io_path.is_dir():
        shutil.copytree(io_path, _io_path(out))
        record["kind"] = "directory"
    else:
        shutil.copy2(io_path, _io_path(out))
        record["kind"] = "file"
    record["backup_relative"] = rel
    record["sha256"] = tree_sha256(out)
    return record


def managed_global_text(existing: str) -> str:
    block = (ROOT / "global" / "AGENTS.md").read_text(encoding="utf-8-sig").strip()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    managed = BEGIN + "\n" + block + "\n" + END
    if pattern.search(existing):
        return pattern.sub(managed, existing).rstrip() + "\n"
    prefix = existing.rstrip()
    return ((prefix + "\n\n") if prefix else "") + managed + "\n"


def managed_global_sha256(path: Path) -> str:
    """中文：只哈希本包拥有的 AGENTS 标记区块，忽略区块外自有内容。

    English: Hash only this package's marked AGENTS block and ignore user-owned surrounding text.
    """
    io_path = _io_path(path)
    if not io_path.is_file():
        return "missing"
    text = io_path.read_text(encoding="utf-8-sig")
    pattern = re.compile(
        re.escape(BEGIN) + r"\r?\n(.*?)\r?\n" + re.escape(END), re.S,
    )
    matches = pattern.findall(text)
    if len(matches) != 1:
        return "invalid-managed-block"
    block = matches[0].strip().replace("\r\n", "\n").replace("\r", "\n") + "\n"
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def _native_async_user_prompt_submit_supported(profile: Optional[Mapping[str, Any]]) -> bool:
    """中文：只有注册表明确给出官方证据时才启用可选 async Hook。

    English: Enable the optional async Hook only with explicit official registry evidence.
    """
    capability = (profile or {}).get("native_async_user_prompt_submit")
    return (
        isinstance(capability, Mapping)
        and capability.get("status") == "SUPPORTED"
        and capability.get("evidence") in {"OFFICIAL_SOURCE_TAG", "OFFICIAL_DOCS_CURRENT"}
    )


def _native_apply_patch_operation_supported(profile: Optional[Mapping[str, Any]]) -> bool:
    """中文：验证冻结的官方 apply_patch Pre/Post schema 证据。

    English: Require frozen official Pre/Post apply_patch schema evidence.
    """
    capability = (profile or {}).get("native_apply_patch_operation")
    return (
        isinstance(capability, Mapping)
        and capability.get("status") == "SUPPORTED"
        and capability.get("evidence") == "OFFICIAL_SOURCE_TAG"
        and capability.get("registration") == "REQUIRED_APPLY_PATCH_PRE_POST"
        and isinstance((profile or {}).get("apply_patch_result_profile"), str)
    )


def hook_fragment(script_path: Path, profile: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    command = '"%s" "%s"' % (sys.executable.replace('"', '\\"'), str(script_path).replace('"', '\\"'))
    gate_path = script_path.with_name("cp_gate.py")
    gate_command = '"%s" "%s"' % (
        sys.executable.replace('"', '\\"'), str(gate_path).replace('"', '\\"'),
    )
    fragment = {
        "PreToolUse": [
            {"matcher": "Agent|spawn_agent", "hooks": [{"type": "command", "command": command, "timeout": 5}]},
            {"matcher": "apply_patch|Edit|Write", "hooks": [{"type": "command", "command": gate_command + " PreToolUse", "timeout": 5}]},
        ],
        "PostToolUse": [
            {"matcher": "apply_patch|Edit|Write", "hooks": [{"type": "command", "command": gate_command + " PostToolUse", "timeout": 5}]},
            {"matcher": "Agent|spawn_agent", "hooks": [{"type": "command", "command": command + " PostToolUse", "timeout": 5}]},
        ],
        "SubagentStart": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "SubagentStop": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "Stop": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "Interrupt": [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}],
    }
    # 中文：UserPromptSubmit 是可选能力；没有可验证的宿主 profile 时完全不注册。
    # English: UserPromptSubmit is optional; omit it entirely without a verified host profile.
    if _native_async_user_prompt_submit_supported(profile):
        fragment["UserPromptSubmit"] = [{"hooks": [{
            "type": "command", "command": command, "timeout": 5, "async": True,
        }]}]
    return fragment


def merge_hooks(path: Path, script_path: Path, profile: Optional[Mapping[str, Any]] = None) -> None:
    data = load_json(path, {}) or {}
    if not isinstance(data, dict):
        raise InstallError("现有 hooks.json 不是 JSON 对象")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError("现有 hooks.json 的 hooks 不是对象")
    fragment = hook_fragment(script_path, profile)
    # 中文：先移除本包旧命令，避免重复安装。
    # English: Remove commands from earlier package versions before adding new entries.
    for event, entries in list(hooks.items()):
        if isinstance(entries, list):
            kept = []
            for entry in entries:
                if not _is_managed_hook_entry(entry):
                    kept.append(entry)
            hooks[event] = kept
    for event, entries in fragment.items():
        hooks.setdefault(event, []).extend(entries)
    write_json_atomic(path, data)


def remove_managed_hooks(path: Path) -> None:
    if not _io_path(path).is_file(): return
    data = load_json(path, {}) or {}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict): return
    for event, entries in list(hooks.items()):
        if isinstance(entries, list):
            hooks[event] = [entry for entry in entries if not _is_managed_hook_entry(entry)]
    write_json_atomic(path, data)


def _is_managed_hook_entry(entry: Any) -> bool:
    """中文：只识别本包拥有的 standalone Hook 命令。

    English: Identify only the standalone Hook command owned by this package.
    """
    if not isinstance(entry, dict):
        return False
    for hook in entry.get("hooks") or []:
        if not isinstance(hook, dict):
            continue
        command = str(hook.get("command") or "").replace("\\", "/").lower()
        if ("cp-assistant-hooks/cp_hook.py" in command
                or "cp-assistant-hooks/cp_gate.py" in command):
            return True
    return False


def _managed_hook_errors(path: Path, script_path: Path,
                         profile: Optional[Mapping[str, Any]] = None) -> List[str]:
    """中文：验证账户级受管 Hook 完整性，同时保留第三方 Hook。

    English: Verify account-managed Hook integrity without constraining third-party Hooks.
    """
    try:
        data = load_json(path, {}) or {}
    except (json.JSONDecodeError, UnicodeError) as exc:
        return ["增强 hooks.json 无法解析: %s" % exc]
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return ["增强 hooks.json 的 hooks 不是对象"]
    expected = hook_fragment(script_path, profile)
    errors: List[str] = []
    for event, entries in expected.items():
        actual = hooks.get(event)
        if not isinstance(actual, list):
            errors.append("增强 Hook 缺少事件 %s" % event)
            continue
        actual_serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                             for item in actual if isinstance(item, dict)]
        expected_serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                               for item in entries]
        for item in expected_serialized:
            if item not in actual_serialized:
                errors.append("增强 Hook 缺少或漂移: %s" % event)
                break
        expected_set = set(expected_serialized)
        for raw, item in zip(actual_serialized, (item for item in actual if isinstance(item, dict))):
            if _is_managed_hook_entry(item) and raw not in expected_set:
                errors.append("增强 Hook 受管条目漂移: %s" % event)
                break
    return errors


def restore_global_agents(path: Path, previous: Optional[Path]) -> None:
    """中文：只恢复本包拥有的 AGENTS 标记区块并保留外部编辑；卸载升级版本时可恢复旧受管区块。

    English: Restore only this package's marked AGENTS block and preserve external edits; uninstalling an upgrade may restore the prior managed block.
    """
    io_path = _io_path(path)
    if not io_path.exists():
        if previous is not None and _io_path(previous).is_file():
            copy_atomic(previous, path)
        return
    current = io_path.read_text(encoding="utf-8-sig")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    prior_block = ""
    if previous is not None and _io_path(previous).is_file():
        old_text = _io_path(previous).read_text(encoding="utf-8-sig")
        old_match = pattern.search(old_text)
        prior_block = old_match.group(0) if old_match else ""
    current_match = pattern.search(current)
    if current_match:
        updated = current[:current_match.start()] + prior_block + current[current_match.end():]
    elif prior_block:
        updated = current.rstrip() + "\n\n" + prior_block + "\n"
    else:
        updated = current
    if updated.strip():
        text_atomic(path, updated)
    elif previous is None:
        remove_path(path)
    else:
        text_atomic(path, "")


def restore_managed_hooks(path: Path, previous: Optional[Path]) -> None:
    """中文：移除当前包 Hook、恢复先前包 Hook，并保留其他 Hook。

    English: Remove current package Hooks, restore prior package Hooks, and keep all other Hooks.
    """
    io_path = _io_path(path)
    if not io_path.exists():
        if previous is not None and _io_path(previous).is_file():
            copy_atomic(previous, path)
        return
    try:
        data = load_json(path, {}) or {}
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise InstallError("现有 hooks.json 无法解析，拒绝覆盖外部文件") from exc
    if not isinstance(data, dict):
        raise InstallError("现有 hooks.json 不是 JSON 对象，拒绝覆盖外部文件")
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        raise InstallError("现有 hooks.json 的 hooks 不是对象，拒绝覆盖外部文件")
    for event, entries in list(hooks.items()):
        if isinstance(entries, list):
            kept = [entry for entry in entries if not _is_managed_hook_entry(entry)]
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event, None)
    if previous is not None and _io_path(previous).is_file():
        old = load_json(previous, {}) or {}
        old_hooks = old.get("hooks") if isinstance(old, dict) else None
        if isinstance(old_hooks, dict):
            for event, entries in old_hooks.items():
                if not isinstance(entries, list):
                    continue
                managed = [entry for entry in entries if _is_managed_hook_entry(entry)]
                if managed:
                    hooks.setdefault(event, []).extend(managed)
    if previous is None and data == {"hooks": {}}:
        remove_path(path)
    else:
        write_json_atomic(path, data)


def manifest() -> Dict[str, Any]:
    return load_json(MANIFEST_PATH, {})


def _validated_skill_dir_name(value: Any, field: str) -> str:
    """中文：Manifest 中的 Skill 只能是单层安全目录名。

    English: A manifest Skill must be one safe, single directory component.
    """
    if not isinstance(value, str) or not SKILL_DIR_NAME_PATTERN.fullmatch(value):
        raise InstallError("Manifest %s 包含不安全的 Skill 目录名: %r" % (field, value))
    return value


def skill_names() -> List[str]:
    values = manifest().get("skills", [])
    if not isinstance(values, list):
        raise InstallError("Manifest skills 必须是数组")
    names: List[str] = []
    for item in values:
        if not isinstance(item, dict) or "name" not in item:
            raise InstallError("Manifest skills 条目必须包含 name")
        name = _validated_skill_dir_name(item["name"], "skills")
        if name in names:
            raise InstallError("Manifest skills 包含重复目录名: %s" % name)
        names.append(name)
    return names


def deprecated_skill_names() -> List[str]:
    """中文：返回需要备份并移除的受管旧 Skill，不把当前 Skill 当作旧目录。

    English: Return managed legacy Skills to back up and remove, excluding current Skills.
    """
    values = manifest().get("deprecated_skills", [])
    if not isinstance(values, list):
        raise InstallError("Manifest deprecated_skills 必须是数组")
    current = set(skill_names())
    names: List[str] = []
    for value in values:
        name = _validated_skill_dir_name(value, "deprecated_skills")
        if name not in current and name not in names:
            names.append(name)
    return names


def agent_files() -> List[Path]:
    return sorted(p for p in (ROOT / "custom-agents").glob("*.toml") if p.is_file())


def state_path(scope: str, repo: Optional[Path] = None) -> Path:
    if scope == "repo":
        assert repo is not None
        return repo / ".codex" / "cp-assistant-v6-state.json"
    return codex_home() / "cp-assistant-v6-state.json"


def backup_root(scope: str, repo: Optional[Path] = None) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-%d" % os.getpid()
    if scope == "repo":
        assert repo is not None
        return repo / ".codex" / "cp-assistant-backups" / stamp
    return codex_home() / "backups" / "cp-assistant-v6" / stamp


def plugin_marketplace_root() -> Path:
    return (Path.home() / ".agents" / "plugins" / "cp-assistant-marketplace").absolute()


def base_marketplace_root() -> Path:
    return (Path.home() / ".agents" / "plugins" / "cp-assistant-base-marketplace").absolute()


def base_state_path() -> Path:
    return codex_home() / BASE_STATE_FILE


def _base_state() -> Dict[str, Any]:
    state = load_json(base_state_path(), {}) or {}
    if not state:
        return {}
    expected_root = str(base_marketplace_root())
    if (state.get("schema_version") != 1 or state.get("package") != PACKAGE
            or state.get("marketplace") != BASE_MARKETPLACE
            or state.get("market_root") != expected_root):
        raise InstallError("基础 Plugin state 无效，拒绝覆盖或降级")
    status = str(state.get("status") or "INSTALLED")
    if status not in {"INSTALLING", "INSTALLED", "RECOVERY_REQUIRED"}:
        raise InstallError("基础 Plugin state 状态未知，拒绝覆盖或降级")
    state["status"] = status
    return state


def plugin_marketplace_payload() -> Path:
    return plugin_marketplace_root() / "plugins" / PACKAGE


def plugin_marketplace_manifest() -> Path:
    return plugin_marketplace_root() / ".agents" / "plugins" / "marketplace.json"


def plugin_cache_root(version: str = VERSION) -> Path:
    return codex_home() / "plugins" / "cache" / MARKETPLACE / PACKAGE / version


def payload_manifest() -> Dict[str, Any]:
    try:
        return load_payload_manifest(ROOT / PAYLOAD_MANIFEST_NAME)
    except PayloadIntegrityError as exc:
        raise InstallError(str(exc)) from exc


def payload_report(root: Path) -> Dict[str, Any]:
    try:
        return verify_payload(root, payload_manifest(), package=PACKAGE, version=VERSION)
    except (PayloadIntegrityError, OSError) as exc:
        raise InstallError("Plugin payload 校验失败 (%s): %s" % (root, exc)) from exc


def _safe_base_state() -> Tuple[Dict[str, Any], Optional[str]]:
    """中文：读取独立基础安装 state，不把可选缺失转换为错误。

    English: Read the independent base-install state without turning an optional absence into an error.
    """
    try:
        return _base_state(), None
    except InstallError as exc:
        return {}, str(exc)


def _action_detail(code: str, action_kind: str, argv: List[str], reason: str,
                   expected_result: str, scope: str = "user") -> Dict[str, Any]:
    """中文：构建 status/doctor 投影使用的机器动作合同。

    English: Build the machine action contract used by status and doctor projections.
    """
    if not argv:
        display = ""
    elif os.name == "nt":
        display = "& " + " ".join("'" + item.replace("'", "''") + "'" for item in argv)
    else:
        import shlex
        display = shlex.join(argv)
    return {
        "schema": "ux-action/1",
        "code": code,
        "action_kind": action_kind,
        "argv": list(argv),
        "working_directory": str(ROOT),
        "display_command": display,
        "reason": reason,
        "expected_result": expected_result,
        "scope": scope.upper(),
    }


def _verify_action(scope: str = "user", mode: str = "plugin", repo_path: Optional[str] = None) -> Dict[str, Any]:
    arguments = [sys.executable, str(ROOT / "scripts" / "package_manager.py"), "verify", "--scope", scope, "--mode", mode]
    if scope == "repo" and repo_path:
        arguments.extend(["--repo-path", str(repo_path)])
    return _action_detail(
        "VERIFY_INSTALLATION", "READ_ONLY",
        arguments,
        "重新读取安装文件、注册和兼容性证据。",
        "输出安装验证通过，且不会执行安装、恢复或修复。",
        scope,
    )


def _ux_capability(capability_id: str, availability: str, reason_codes: List[str],
                   evidence_level: str) -> Dict[str, Any]:
    return {"id": capability_id, "availability": availability,
            "reason_codes": sorted(set(reason_codes)), "evidence_level": evidence_level}


def _ux_summary(data: Mapping[str, Any]) -> Dict[str, Any]:
    """中文：只投影已观察的组件事实；配置不作为运行时执行证明。

    English: Project observed component facts; configuration is not runtime enforcement proof.
    """
    scope, mode = str(data.get("scope") or "user"), str(data.get("mode") or "plugin")
    state = data.get("state") if isinstance(data.get("state"), Mapping) else {}
    components = state.get("components") if isinstance(state.get("components"), Mapping) else {}
    activation = data.get("base_activation") if isinstance(data.get("base_activation"), Mapping) else {}
    host = data.get("host_compatibility") if isinstance(data.get("host_compatibility"), Mapping) else {}
    issues = data.get("component_errors") if isinstance(data.get("component_errors"), Mapping) else {}
    capabilities: List[Dict[str, Any]] = []
    causes: List[Dict[str, str]] = []
    affected: List[str] = []
    overall = "PASS"
    action: Optional[Dict[str, Any]] = None

    def add(name: str, availability: str, reasons: List[str], level: str,
            severity: Optional[str] = None) -> None:
        nonlocal overall
        capabilities.append(_ux_capability(name, availability, reasons, level))
        if severity:
            affected.append(name)
            causes.append({"id": name, "detail": "; ".join(reasons)})
            if severity == "ERROR" or overall == "PASS":
                overall = severity

    base_active = bool(activation.get("active"))
    checked = bool(activation.get("checked", False))
    base_errors = list(issues.get("base") or [])
    if scope == "repo":
        add("base-plugin", "NOT_APPLICABLE", ["ACCOUNT_REGISTRATION_OUTSIDE_SCOPE"], "NOT_CHECKED")
        if data.get("git_repository") is False:
            add("repository-skills", "NOT_APPLICABLE", ["NON_GIT_DIRECTORY"], "NOT_CHECKED")
        elif not state:
            add("repository-skills", "NOT_ENABLED", ["OPTIONAL_REPO_INSTALLATION_ABSENT"], "NOT_CHECKED")
        elif base_errors:
            add("repository-skills", "UNAVAILABLE", base_errors, "INSTALLATION", "ERROR")
        else:
            add("repository-skills", "AVAILABLE", ["REPO_INSTALLATION_FILES_PRESENT"], "INSTALLATION")
        available = "基础文件与说明任务可继续；仓库级安装按本次检查结果显示"
    else:
        if not checked and not base_active:
            add("base-plugin", "UNKNOWN", [str(activation.get("detail") or "HOST_SAMPLE_UNAVAILABLE")],
                "NOT_CHECKED", "DEGRADED")
        elif not base_active:
            add("base-plugin", "UNAVAILABLE", ["BASE_NOT_ACTIVE"], "REGISTRATION", "ERROR")
        elif base_errors:
            add("base-plugin", "UNAVAILABLE", base_errors, "INSTALLATION", "ERROR")
        else:
            add("base-plugin", "AVAILABLE", ["BASE_VERIFIED"],
                "INSTALLATION" if mode == "standalone" else "REGISTRATION")
        available = ("基础模式正常；已安装增强能力按实际状态显示" if base_active and not base_errors
                     else "当前无法确认本插件基础能力" if not checked else "本插件基础能力尚不可用")
    enhancement = components.get("enhancement")
    selected = bool(data.get("enhancement_selected", isinstance(enhancement, Mapping)))
    if scope != "user":
        add("enhancement", "NOT_APPLICABLE", ["ACCOUNT_ENHANCEMENT_OUTSIDE_SCOPE"], "NOT_CHECKED")
    elif not selected:
        add("enhancement", "NOT_ENABLED", ["OPTIONAL_NOT_ENABLED"], "NOT_CHECKED")
    else:
        errors = list(issues.get("enhancement") or [])
        if errors:
            add("enhancement", "UNAVAILABLE", errors, "INSTALLATION", "DEGRADED")
        elif host.get("compatible") is False:
            add("enhancement", "BLOCKED", [str(host.get("status") or "HOST_INCOMPATIBLE")],
                "HOST_CHECK", "DEGRADED")
        elif not isinstance(enhancement, Mapping) or enhancement.get("status") not in {"MANAGED", "INSTALLED", "PLUGIN_MANAGED"}:
            add("enhancement", "UNKNOWN", ["ENHANCEMENT_STATE_UNKNOWN"], "NOT_CHECKED", "DEGRADED")
        else:
            add("enhancement", "AVAILABLE", ["ENHANCEMENT_CHECKED"], "INSTALLATION")
    for key in ("mode_error", "state_error", "base_state_error", "transaction_error", "sample_error"):
        if data.get(key):
            add(key, "UNKNOWN" if key == "sample_error" else "BLOCKED", [str(data[key])],
                "INSTALLATION", "DEGRADED" if key == "sample_error" else "ERROR")
    if data.get("duplicate_registration"):
        add("plugin-registration", "BLOCKED", ["DUPLICATE_BASE_AND_ENHANCEMENT_REGISTRATION"],
            "REGISTRATION", "ERROR")
    transaction = data.get("live_transaction")
    if transaction:
        add("installation-transaction", "BLOCKED", ["TRANSACTION_INCOMPLETE"], "INSTALLATION", "ERROR")
        args = [sys.executable, str(ROOT / "scripts" / "package_manager.py"), "recover", "--scope", scope]
        if scope == "repo" and data.get("repo_path"):
            args.extend(["--repo-path", str(data["repo_path"])])
        action = _action_detail("RECOVER_INSTALLATION_TRANSACTION", "WRITE", args,
                                "存在未收敛安装事务。", "显式恢复既有事务后重新诊断。", scope)
    elif data.get("mode_error") == "REQUESTED_MODE_MISMATCH":
        args = [sys.executable, str(ROOT / "scripts" / "package_manager.py"), "status", "--scope", scope]
        if scope == "repo" and data.get("repo_path"):
            args.extend(["--repo-path", str(data["repo_path"])])
        action = _action_detail("READ_INSTALLED_MODE", "READ_ONLY", args,
                                "Requested mode differs from managed state.", "Read the actual installed mode.", scope)
    elif any(data.get(key) for key in ("state_error", "base_state_error", "transaction_error", "mode_error")):
        action = _action_detail("INSPECT_MANAGED_STATE", "MANUAL", [],
                                "受管状态无法可靠读取。", "核对受管状态与已知备份，保留未知文件。", scope)
    elif affected:
        action = _verify_action(scope, mode, data.get("repo_path"))
        if scope == "user" and (not checked or not base_active):
            action = _action_detail("CHECK_PLUGIN_REGISTRATION", "READ_ONLY", ["codex", "plugin", "list", "--json"],
                                    "基础 Plugin 尚未通过宿主注册读回。", "确认 installed/enabled/version 后再进行下一步。")
            records = data.get("registrations") or {}
            if checked and records:
                record = records.get("base") or records.get("enhancement")
                if record and record.get("installed") and not record.get("enabled"):
                    action = _action_detail("ENABLE_INSTALLED_PLUGIN", "WRITE",
                                            ["codex", "plugin", "add", str(record["plugin_id"])],
                                            "The installed Plugin is disabled.", "Verify the enabled registration.")
                elif not record and not state and not data.get("base_state"):
                    args = (["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                             str(ROOT / "scripts" / "install-base.ps1")] if os.name == "nt" else
                            ["sh", str(ROOT / "scripts" / "install-base.sh")])
                    action = _action_detail("INSTALL_BASE_PLUGIN", "WRITE", args,
                                            "The base Plugin is not installed.", "Verify the base Plugin registration.")
    control_checks = data.get("control_checks") or {}
    for name, default in (("controlled-write", "OPERATION_AUTHORIZATION_NOT_EVALUATED"),
                          ("delegation-budget", "TASK_BUDGET_NOT_EVALUATED")):
        control = control_checks.get(name) or {"availability": "NOT_APPLICABLE", "reason": default}
        availability = control["availability"]
        add(name, availability, [control["reason"]], "NOT_CHECKED",
            "ERROR" if availability == "BLOCKED" else "DEGRADED" if availability == "UNKNOWN" else None)
        if availability == "BLOCKED" and action is None:
            action = _action_detail("RESTORE_CONTROL_PREREQUISITES", "MANUAL", [],
                                    control["reason"], "Restore the required runtime or task binding; keep the control enabled.", scope)
    return {"schema": "ux-summary/1", "overall": overall, "available": available,
            "affected": list(dict.fromkeys(affected)), "cause": causes,
            "capabilities": sorted(capabilities, key=lambda item: item["id"]),
            "next_action_detail": action}


def _merge_doctor_checks_into_ux(ux: Mapping[str, Any], checks: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """中文：让 doctor 的检查级错误与能力级投影保持同一终态。

    English: Keep doctor check failures aligned with the capability-level projection.
    """
    merged = dict(ux)
    affected = list(ux.get("affected") or [])
    causes = list(ux.get("cause") or [])
    errors = [item for item in checks if item.get("status") == "ERROR"]
    warnings = [item for item in checks if item.get("status") == "WARN"]
    for item in errors + warnings:
        check_id = str(item.get("id") or "unknown")
        if check_id not in affected:
            affected.append(check_id)
        if not any(isinstance(cause, Mapping) and cause.get("id") == check_id for cause in causes):
            causes.append({"id": check_id, "detail": str(item.get("detail") or "doctor check requires attention")})
    current = str(ux.get("overall") or "UNKNOWN")
    if errors:
        merged["overall"] = "ERROR"
    elif warnings and current == "PASS":
        merged["overall"] = "DEGRADED"
        merged["available"] = "基础能力可继续使用，但存在需核对的 doctor 检查项"
    merged["affected"] = affected
    merged["cause"] = causes
    if (errors or warnings) and not merged.get("next_action_detail"):
        merged["next_action_detail"] = _verify_action()
    return merged


def doctor_summary(data: Mapping[str, Any]) -> Dict[str, Any]:
    """中文：为常规调用者提供可行动摘要；完整机器字段仍由 JSON 输出。

    English: Provide an actionable ordinary-user summary while retaining JSON details.
    """
    checks = data.get("checks") if isinstance(data.get("checks"), list) else []
    raw_ux = data.get("ux") if isinstance(data.get("ux"), Mapping) else _ux_summary(data)
    ux = _merge_doctor_checks_into_ux(raw_ux, [item for item in checks if isinstance(item, Mapping)])
    action = ux.get("next_action_detail") or {}
    return {"overall": ux["overall"], "available": ux["available"],
            "affected": ux["affected"], "cause": ux["cause"],
            "next_action": action.get("display_command") or action.get("expected_result") or "可直接开始任务；需要详细状态时运行 doctor --json。",
            "ux": ux}


def migrate_state_v1_to_v2(value: Mapping[str, Any], scope: str, mode: str) -> Dict[str, Any]:
    """中文：保留全部既有和未知字段，同时明确 V7 身份字段。

    English: Preserve all prior and unknown fields while making the V7 identity fields explicit.
    """
    if not value:
        return {}
    schema = value.get("schema_version")
    if schema not in {1, 2}:
        raise InstallError("安装状态 schema 未知，拒绝覆盖: %s" % schema)
    migrated = dict(value)
    if value.get("scope") not in {None, scope}:
        raise InstallError("安装状态 scope 不匹配，拒绝迁移")
    old_mode = str(value.get("mode") or mode)
    if old_mode not in {"plugin", "standalone"}:
        raise InstallError("安装状态 mode 无效，拒绝迁移")
    if scope == "user" and not isinstance(value.get("managed_hashes", {}), dict):
        raise InstallError("账户安装状态 managed_hashes 无效")
    if value.get("backup") is not None and not isinstance(value.get("backup"), str):
        raise InstallError("安装状态 backup 无效")
    migrated["schema_version"] = 2
    migrated["scope"] = scope
    migrated["mode"] = old_mode
    if schema == 1:
        migrated["migrated_from_schema"] = 1
    return migrated


def migrate_state_to_v3(value: Mapping[str, Any], scope: str, mode: str) -> Dict[str, Any]:
    """中文：保守读取旧状态，禁止其声明宿主兼容。

    English: Read legacy state conservatively; it cannot claim host compatibility.
    """
    if not value:
        return {}
    schema = value.get("schema_version")
    if schema in {1, 2}:
        migrated = migrate_state_v1_to_v2(value, scope, mode)
        migrated["schema_version"] = 3
        migrated["migrated_from_schema"] = schema
        migrated["compatibility_status"] = "LEGACY_HOST_PROFILE_UNKNOWN"
        return migrated
    if schema != 3:
        raise InstallError("安装状态 schema 未知，拒绝覆盖: %s" % schema)
    migrated = dict(value)
    if value.get("scope") not in {None, scope}:
        raise InstallError("安装状态 scope 不匹配，拒绝迁移")
    old_mode = str(value.get("mode") or mode)
    if old_mode not in {"plugin", "standalone"}:
        raise InstallError("安装状态 mode 无效，拒绝迁移")
    migrated["scope"] = scope
    migrated["mode"] = old_mode
    return migrated


def capability_preference_migration(value: Mapping[str, Any]) -> Dict[str, Any]:
    """中文：只按明确旧来源生成偏好迁移计划，门禁和操作证据永不参与。

    English: Build a preference migration plan only from explicit legacy sources; gate and operation evidence never participate.
    """
    preference = value.get("capability_preference")
    classification = "UNKNOWN_OFF"
    evidence = "missing-or-unowned"
    if isinstance(preference, dict):
        source = str(preference.get("source") or "")
        mode = str(preference.get("mode") or "").upper()
        if source == "USER" and mode == "OFF":
            classification, evidence = "USER_OFF", "owned-explicit-user-preference"
        elif source in {"USER", "INSTALLER", "MANAGED"} and mode == "ON":
            classification, evidence = "LEGACY_ON", "owned-explicit-legacy-on"
    elif str(value.get("package") or PACKAGE) == PACKAGE \
            and str(value.get("version") or "") in AUTO_MIGRATION_SOURCES \
            and value.get("schema_version") in {1, 2, 3}:
        classification, evidence = "DEFAULT_OFF", "known-version-installer-default"
    mapping = {
        "DEFAULT_OFF": ("AUTO", "BASIC"), "USER_OFF": ("OFF", None),
        "UNKNOWN_OFF": ("OFF", None), "LEGACY_ON": ("AUTO", "BASIC"),
    }
    configured_mode, max_level = mapping[classification]
    return {"schema_version":"capability-preference-migration/1", "classification":classification,
            "evidence":evidence, "configured_mode":configured_mode, "max_level":max_level,
            "authorization":False, "scan_consent":False, "gate_policy_excluded":True,
            "gate_task_excluded":True, "operation_v2_excluded":True,
            "application":"PROJECT_LAZY_CAS_AFTER_IDENTITY_BINDING"}


def _merged_marketplace_manifest(existing: Any, marketplace_profile: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """中文：只合并本包拥有的字段并保留未知元数据。

    English: Merge only fields owned by this package and preserve unknown metadata.
    """
    if existing is not None and not isinstance(existing, dict):
        raise InstallError("Marketplace manifest 顶层必须是 JSON object")
    data = dict(existing or {})
    raw_plugins = data.get("plugins", [])
    if not isinstance(raw_plugins, list) or any(not isinstance(item, dict) for item in raw_plugins):
        raise InstallError("Marketplace plugins 必须是 object array")
    target_items = [item for item in raw_plugins if item.get("name") == PACKAGE]
    if len(target_items) > 1:
        raise InstallError("Marketplace 中存在重复的目标 Plugin 条目")
    plugins = [dict(item) for item in raw_plugins if item.get("name") != PACKAGE]
    plugins.append({"name": PACKAGE,
                    "source": {"source": "local", "path": "./plugins/%s" % PACKAGE},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity"})
    data["name"] = MARKETPLACE
    profile = marketplace_profile or COMPATIBILITY_REGISTRY["profiles"]["marketplace"]["local-interface-v2"]
    interface = data.get("interface", {})
    if interface is not None and not isinstance(interface, dict):
        raise InstallError("Marketplace interface 必须是 JSON object")
    merged_interface = dict(interface or {})
    merged_interface["displayName"] = str(profile["display_name"])
    data["interface"] = merged_interface
    # 中文：owner 不是本包受管字段；即使旧值未知也必须保留。
    # English: owner is not managed by this package and must be preserved even when unknown.
    data["plugins"] = plugins
    return data


def _copy_plugin_payload_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        _io_path(src),
        _io_path(dst),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def plugin_payload_source(tmp: Path) -> Path:
    name = PACKAGE
    out = tmp / name
    out.mkdir(parents=True)
    for rel in (".codex-plugin", "skills", "hooks", "runtime"):
        _copy_plugin_payload_tree(ROOT / rel, out / rel)
    shutil.copy2(_io_path(ROOT / PAYLOAD_MANIFEST_NAME), _io_path(out / PAYLOAD_MANIFEST_NAME))
    payload_report(out)
    return out


def _codex_executable() -> str:
    configured = os.environ.get("CP_ASSISTANT_CODEX_EXECUTABLE", "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve(strict=True)
        if not candidate.is_file():
            raise InstallError("CP_ASSISTANT_CODEX_EXECUTABLE 不是文件")
        return str(candidate)
    exe = shutil.which("codex")
    if not exe:
        raise InstallError("未找到 codex CLI；Plugin 模式需要已验证的 Codex CLI 版本。可改用 --mode standalone")
    return exe


def _codex_available() -> bool:
    """中文：返回已配置或通过 PATH 发现的 Codex 是否可用。

    English: Return whether a configured or PATH-discovered Codex executable is available.
    """
    configured = os.environ.get("CP_ASSISTANT_CODEX_EXECUTABLE", "").strip()
    if configured:
        try:
            return Path(configured).expanduser().resolve(strict=True).is_file()
        except OSError:
            return False
    return shutil.which("codex") is not None


def _run_codex(args: List[str], timeout: int = 60, check: bool = True,
               home_override: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    cmd = [_codex_executable()] + args
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home_override if home_override is not None else codex_home())
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env, timeout=timeout)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InstallError("Codex CLI 执行失败: %s；%s" % (" ".join(cmd), detail[-2000:]))
    return result


def _activate_plugin(market: Path) -> None:
    # 中文：在 0.150.1 中，marketplace add 接收市场根目录，plugin add 随后安装并启用插件。
    # English: In 0.150.1, marketplace add accepts the root, then plugin add installs and enables it.
    _run_codex(["plugin", "marketplace", "add", str(market)])
    _run_codex(["plugin", "add", "%s@%s" % (PACKAGE, MARKETPLACE)])


def _deactivate_plugin(check: bool = True) -> None:
    result = _run_codex(["plugin", "remove", "%s@%s" % (PACKAGE, MARKETPLACE)], check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        # 中文：回滚或卸载时，目标已经不存在属于可接受状态。
        # English: An already-absent target is acceptable during rollback or uninstall.
        lowered = detail.lower()
        if not any(token in lowered for token in ("not installed", "not found", "no plugin")):
            raise InstallError("Codex Plugin 卸载失败: %s" % detail[-2000:])


def _deactivate_base_plugin(check: bool = True) -> None:
    result = _run_codex(["plugin", "remove", "%s@%s" % (PACKAGE, BASE_MARKETPLACE)], check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().lower()
        if not any(token in detail for token in ("not installed", "not found", "no plugin")):
            raise InstallError("基础 Plugin 卸载失败: %s" % detail[-2000:])


def _remove_base_marketplace(check: bool = True) -> None:
    result = _run_codex(["plugin", "marketplace", "remove", BASE_MARKETPLACE], check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().lower()
        if not any(token in detail for token in ("not configured", "not found", "no marketplace")):
            raise InstallError("基础 Marketplace 注销失败: %s" % detail[-2000:])


def _base_plugin_active() -> bool:
    result = _run_codex(["plugin", "list", "--json"], check=False)
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout or "{}")
        rows = list(payload.get("installed") or []) + list(payload.get("available") or [])
    except (TypeError, ValueError):
        return False
    return any(isinstance(item, dict) and item.get("pluginId") == "%s@%s" % (PACKAGE, BASE_MARKETPLACE)
               and item.get("installed") is True and item.get("enabled") is True for item in rows)


def _normalized_mode(value: Any) -> str:
    mode = str(value or "")
    return mode if mode in {"plugin", "standalone"} else "plugin"


def _mode_error(value: Any) -> Optional[str]:
    if value in (None, "", "plugin", "standalone"):
        return None
    return "INVALID_PERSISTED_MODE"


def _base_activation_detail(mode: str, active: bool) -> str:
    if mode == "standalone":
        return "独立模式基础 Skill 可用" if active else "独立模式基础 Skill 未核验"
    return "base Plugin active" if active else "base Plugin not active"


def _base_capability_active(codex_checked: bool, mode: str, base_state: Mapping[str, Any],
                            state: Mapping[str, Any], plugin_active: bool,
                            base_plugin_active: bool) -> bool:
    """中文：组合独立基础注册或明确迁移后的基础归属与宿主读回。

    English: Combine independent base registration or explicit migrated ownership with host readback.
    """
    components = state.get("components") if isinstance(state.get("components"), Mapping) else {}
    base_component = components.get("base") if isinstance(components.get("base"), Mapping) else {}
    if mode == "standalone" and base_component.get("status") == "STANDALONE_SKILLS":
        return True
    if not codex_checked:
        return False
    if base_state and base_plugin_active:
        return True
    return mode == "plugin" and plugin_active and base_component.get("status") == "PLUGIN_MANAGED"


def _remove_marketplace(check: bool = True) -> None:
    result = _run_codex(["plugin", "marketplace", "remove", MARKETPLACE], check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        lowered = detail.lower()
        if not any(token in lowered for token in ("not configured", "not found", "no marketplace")):
            raise InstallError("Codex Marketplace 注销失败: %s" % detail[-2000:])


def _remove_empty_marketplace_dirs() -> None:
    """中文：只移除本 Marketplace 创建的空目录，绝不递归删除。

    English: Remove only empty directories created for this Marketplace and never delete recursively.
    """
    market = plugin_marketplace_root()
    for candidate in (market / "plugins", market / ".agents" / "plugins", market / ".agents", market):
        try:
            _io_path(candidate).rmdir()
        except (FileNotFoundError, OSError):
            pass


def _codex_version_text() -> str:
    result = _run_codex(["--version"], check=False)
    return (result.stdout or result.stderr or "").rstrip("\r\n")


def _standalone_hook_profile() -> Optional[Dict[str, Any]]:
    """中文：仅用 ``codex --version`` 解析 standalone Hook 能力，不触发 Plugin CLI。

    English: Resolve standalone Hook capability only from ``codex --version`` without invoking Plugin CLI.
    """
    try:
        version = parse_codex_version_output(_codex_version_text())
        return profile_for_version(COMPATIBILITY_REGISTRY, version)
    except (CompatibilityError, InstallError, OSError):
        return None


def _plugin_activation_status(expected_version: Optional[str] = None) -> Tuple[bool, str]:
    result = _run_codex(["plugin", "list", "--json"], check=False)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "codex plugin list failed").strip()
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False, "codex plugin list --json 返回了非 JSON 数据"
    try:
        host_version = parse_codex_version_output(_codex_version_text())
        host_profile = profile_for_version(COMPATIBILITY_REGISTRY, host_version)
        json_profile = COMPATIBILITY_REGISTRY["profiles"]["plugin_json"][host_profile["plugin_json_profile"]]
        normalized = normalize_plugin_list(
            data, PACKAGE, MARKETPLACE, expected_version, json_profile,
        )
    except CompatibilityError as exc:
        return False, "codex plugin list --json 契约不兼容: %s" % exc
    if normalized is None:
        return False, "未在 Codex installed 列表中发现 %s@%s" % (PACKAGE, MARKETPLACE)
    return True, json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _verify_restored_plugin(previous: Mapping[str, Any]) -> None:
    if not previous.get("active"):
        return
    version = str(previous.get("version") or "")
    active, detail = _plugin_activation_status(version or None)
    if not active:
        raise InstallError("旧 Plugin 重新激活读回失败: %s" % detail)
    cache_value = str(previous.get("cache_path") or "")
    expected = str(previous.get("cache_tree_sha256") or "")
    if cache_value and expected:
        cache = Path(cache_value)
        if not cache.is_dir() or tree_sha256(cache) != expected:
            raise InstallError("旧 Plugin cache 恢复后 digest 不匹配: %s" % cache)


def _probe_plugin_host(timeout: Optional[int] = None) -> Dict[str, Any]:
    """中文：读取已验证 Codex CLI 版本的 Plugin 宿主能力，不修改状态。

    English: Read the Plugin host capability profile for verified Codex CLI versions without
    changing state.
    """
    run_options = {"timeout": timeout} if timeout is not None else {}
    if timeout is None:
        version_text = _codex_version_text()
    else:
        version_result = _run_codex(["--version"], check=False, **run_options)
        version_text = (version_result.stdout or version_result.stderr or "").rstrip("\r\n")
    try:
        version = parse_codex_version_output(version_text)
        version_profile = profile_for_version(COMPATIBILITY_REGISTRY, version)
        version_ok = True
        version_error = ""
    except CompatibilityError as exc:
        version = ""
        version_profile = None
        version_ok = False
        version_error = str(exc)
    expected_evidence = version_profile["probe_evidence"] if version_profile else {}
    version_output_digest = hashlib.sha256(version_text.encode("utf-8")).hexdigest()
    version_contract_ok = bool(
        version_profile
        and version_output_digest == expected_evidence.get("version_output_sha256")
    )
    result = _run_codex(["plugin", "list", "--json"], check=False, **run_options)
    try:
        data = json.loads(result.stdout or "")
    except json.JSONDecodeError:
        data = None
    normalized_target = None
    registrations: Dict[str, Any] = {"checked": False, "base": None, "enhancement": None}
    if result.returncode == 0 and version_profile is not None:
        try:
            diagnostic_profile = COMPATIBILITY_REGISTRY["profiles"]["plugin_json"][version_profile["plugin_json_profile"]]
            registrations["base"] = normalize_plugin_list(
                data, PACKAGE, BASE_MARKETPLACE, None, diagnostic_profile,
                require_active=False, other_marketplaces=(MARKETPLACE,),
            )
            registrations["enhancement"] = normalize_plugin_list(
                data, PACKAGE, MARKETPLACE, None, diagnostic_profile,
                require_active=False, other_marketplaces=(BASE_MARKETPLACE,),
            )
            registrations["checked"] = True
        except CompatibilityError:
            registrations = {"checked": False, "base": None, "enhancement": None,
                             "detail": "PLUGIN_SCHEMA_UNVERIFIED"}
    list_error = ""
    list_ok = False
    if result.returncode == 0 and version_profile is not None:
        try:
            json_profile = COMPATIBILITY_REGISTRY["profiles"]["plugin_json"][version_profile["plugin_json_profile"]]
            normalized_target = normalize_plugin_list(data, PACKAGE, MARKETPLACE, None, json_profile)
            list_ok = True
        except CompatibilityError as exc:
            # 中文：基础入口拥有独立 marker；升级前允许它作为唯一已安装身份通过同一 schema 校验。
            # English: The base entry has its own marker; before upgrade it may be the sole installed identity under the same schema.
            try:
                if _base_state():
                    normalized_target = normalize_plugin_list(data, PACKAGE, BASE_MARKETPLACE, None, json_profile)
                    list_ok = True
                else:
                    list_error = str(exc)
            except (CompatibilityError, InstallError):
                list_error = str(exc)
    elif result.returncode != 0:
        list_error = (result.stderr or result.stdout or "codex plugin list failed").strip()
    commands: Dict[str, Dict[str, Any]] = {}
    command_contract_errors: List[str] = []
    for name, args in {
        "marketplace_add": ["plugin", "marketplace", "add", "--help"],
        "marketplace_remove": ["plugin", "marketplace", "remove", "--help"],
        "plugin_add": ["plugin", "add", "--help"],
        "plugin_remove": ["plugin", "remove", "--help"],
    }.items():
        probe = _run_codex(args, check=False, **run_options)
        output = (probe.stdout or probe.stderr or "").rstrip("\r\n")
        output_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
        expected_digest = expected_evidence.get(f"{name}_help_sha256")
        contract_ok = probe.returncode == 0 and output_digest == expected_digest
        commands[name] = {"ok": probe.returncode == 0, "sha256": output_digest}
        if not contract_ok:
            command_contract_errors.append(name)
    executable = Path(_codex_executable()).resolve(strict=True)
    binding = {
        "codex_version": version,
        "executable_path": str(executable),
        "executable_sha256": sha256_file(executable),
        "registry_schema": COMPATIBILITY_REGISTRY["schema_version"],
        "registry_digest": canonical_digest(COMPATIBILITY_REGISTRY),
        "marketplace_profile": version_profile["marketplace_profile"] if version_profile else None,
        "plugin_cli_profile": version_profile["plugin_cli_profile"] if version_profile else None,
        "plugin_json_profile": version_profile["plugin_json_profile"] if version_profile else None,
        "hook_profile": version_profile["hook_profile"] if version_profile else None,
        "apply_patch_result_profile": version_profile["apply_patch_result_profile"] if version_profile else None,
        "commands": commands,
        "plugin_list_contract": list_ok,
    }
    binding["capability_digest"] = canonical_digest(binding)
    return {
        **binding,
        "codex_version_output": version_text,
        "version_ok": version_ok,
        "version_error": version_error,
        "version_contract_ok": version_contract_ok,
        "version_output_sha256": version_output_digest,
        "plugin_list_json": list_ok,
        "plugin_list_error": list_error[-2000:],
        "command_contract_errors": command_contract_errors,
        "normalized_target": normalized_target,
        "registrations": registrations,
        "ok": version_ok and version_contract_ok and list_ok
              and all(item["ok"] for item in commands.values())
              and not command_contract_errors,
    }


def _legacy_marketplace_repairable() -> bool:
    """中文：变更前只识别已知受管版本的确切 Marketplace 清单漂移。

    English: Recognize only exact Marketplace manifest drift from known managed versions before mutation.
    """
    try:
        state = load_json(state_path("user"), {})
        manifest = load_json(plugin_marketplace_manifest(), {})
    except Exception:
        return False
    if not isinstance(state, dict) or not isinstance(manifest, dict):
        return False
    if state.get("package") != PACKAGE or state.get("mode") != "plugin":
        return False
    if str(state.get("version") or "") not in REPAIRABLE_MARKETPLACE_STATE_VERSIONS:
        return False
    if state.get("schema_version") not in {1, 2, 3} or manifest.get("name") != MARKETPLACE:
        return False
    return any(isinstance(item, dict) and item.get("name") == PACKAGE
               for item in manifest.get("plugins", []))


def _host_binding(profile: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "codex_version", "executable_path", "executable_sha256", "registry_schema",
        "registry_digest", "marketplace_profile", "plugin_cli_profile",
        "plugin_json_profile", "hook_profile", "apply_patch_result_profile", "commands", "plugin_list_contract",
        "capability_digest",
    )
    return {key: profile.get(key) for key in keys}


_HOST_BINDING_KEYS = {
    "codex_version", "executable_path", "executable_sha256", "registry_schema",
    "registry_digest", "marketplace_profile", "plugin_cli_profile",
    "plugin_json_profile", "hook_profile", "apply_patch_result_profile", "commands", "plugin_list_contract",
    "capability_digest",
}
_HOST_COMMAND_KEYS = {
    "marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove",
}


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_host_binding(binding: Any) -> bool:
    """中文：独立于外层摘要验证已保存的宿主绑定。

    English: Validate a stored host binding independently of its outer digest.
    """
    if not isinstance(binding, dict) or set(binding) != _HOST_BINDING_KEYS:
        return False
    version = binding.get("codex_version")
    try:
        version_profile = profile_for_version(COMPATIBILITY_REGISTRY, version)
    except CompatibilityError:
        return False
    if not isinstance(binding.get("executable_path"), str) or not binding["executable_path"]:
        return False
    if not _valid_sha256(binding.get("executable_sha256")) or not _valid_sha256(binding.get("registry_digest")):
        return False
    if binding.get("registry_schema") != COMPATIBILITY_REGISTRY["schema_version"]:
        return False
    if binding.get("registry_digest") != canonical_digest(COMPATIBILITY_REGISTRY):
        return False
    for key in ("marketplace_profile", "plugin_cli_profile", "plugin_json_profile",
                "hook_profile", "apply_patch_result_profile"):
        if binding.get(key) != version_profile[key]:
            return False
    commands = binding.get("commands")
    if not isinstance(commands, dict) or set(commands) != _HOST_COMMAND_KEYS:
        return False
    for command in commands.values():
        if not isinstance(command, dict) or set(command) != {"ok", "sha256"}:
            return False
        if command.get("ok") is not True or not _valid_sha256(command.get("sha256")):
            return False
    if binding.get("plugin_list_contract") is not True:
        return False
    expected_capability = dict(binding)
    capability_digest = expected_capability.pop("capability_digest", None)
    return _valid_sha256(capability_digest) and capability_digest == canonical_digest(expected_capability)


def _host_identity_without_plugin_list(profile: Mapping[str, Any]) -> Dict[str, Any]:
    binding = _host_binding(profile)
    binding.pop("plugin_list_contract", None)
    binding.pop("capability_digest", None)
    return binding


def _compatibility_snapshot(profile: Mapping[str, Any], payload_digest: str,
                            readback_detail: str) -> Dict[str, Any]:
    try:
        normalized = json.loads(readback_detail)
    except json.JSONDecodeError as exc:
        raise InstallError("Plugin 规范化读回无法写入兼容快照") from exc
    if not isinstance(normalized, dict):
        raise InstallError("Plugin 规范化读回不是 object")
    binding = _host_binding(profile)
    return {
        "schema_version": 1,
        "host_binding": binding,
        "host_binding_digest": canonical_digest(binding),
        "plugin_readback_digest": canonical_digest(normalized),
        "payload_digest": payload_digest,
        "captured_at": time.time(),
    }


def _host_compatibility_status(state: Mapping[str, Any], observed: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    if state.get("schema_version") != 3:
        return {"status": "LEGACY_HOST_PROFILE_UNKNOWN", "compatible": False}
    snapshot = state.get("compatibility_snapshot")
    required = {
        "schema_version", "host_binding", "host_binding_digest",
        "plugin_readback_digest", "payload_digest", "captured_at",
    }
    if not isinstance(snapshot, dict) or set(snapshot) != required or snapshot.get("schema_version") != 1:
        return {"status": "COMPATIBILITY_SNAPSHOT_INVALID", "compatible": False}
    stored_binding = snapshot.get("host_binding")
    payload_identity = state.get("payload_identity")
    if (not _validate_host_binding(stored_binding)
            or not _valid_sha256(snapshot.get("host_binding_digest"))
            or canonical_digest(stored_binding) != snapshot.get("host_binding_digest")
            or not _valid_sha256(snapshot.get("plugin_readback_digest"))
            or not _valid_sha256(snapshot.get("payload_digest"))
            or not isinstance(snapshot.get("captured_at"), (int, float))
            or isinstance(snapshot.get("captured_at"), bool)
            or not isinstance(payload_identity, dict)
            or snapshot.get("payload_digest") != payload_identity.get("manifest_digest")):
        return {"status": "COMPATIBILITY_SNAPSHOT_INVALID", "compatible": False}
    try:
        current = observed if observed is not None else _probe_plugin_host()
    except Exception as exc:
        return {"status": "HOST_PROBE_FAILED", "compatible": False, "detail": str(exc)}
    if not current.get("ok"):
        return {
            "status": "HOST_DRIFT_REINSTALL_REQUIRED", "compatible": False,
            "detail": current.get("version_error") or current.get("plugin_list_error") or "capability probe failed",
        }
    current_binding = _host_binding(current)
    current_digest = canonical_digest(current_binding)
    if current_digest != snapshot["host_binding_digest"]:
        return {
            "status": "HOST_DRIFT_REINSTALL_REQUIRED", "compatible": False,
            "stored_host_binding_digest": snapshot["host_binding_digest"],
            "current_host_binding_digest": current_digest,
        }
    return {
        "status": "HOST_COMPATIBLE", "compatible": True,
        "host_binding_digest": current_digest,
    }


def _isolated_plugin_preflight(profile: Mapping[str, Any]) -> Dict[str, Any]:
    """中文：账户写入前在隔离 CODEX_HOME 中验证添加、列出与移除。

    English: Exercise add/list/remove against an isolated CODEX_HOME before account writes.
    """
    version_profile = profile_for_version(COMPATIBILITY_REGISTRY, str(profile["codex_version"]))
    marketplace_profile = COMPATIBILITY_REGISTRY["profiles"]["marketplace"][
        version_profile["marketplace_profile"]
    ]
    json_profile = COMPATIBILITY_REGISTRY["profiles"]["plugin_json"][
        version_profile["plugin_json_profile"]
    ]
    with tempfile.TemporaryDirectory(prefix="cp-plugin-preflight-") as td:
        root = Path(td)
        isolated_home = root / "codex-home"
        market = root / "marketplace"
        isolated_home.mkdir(parents=True)
        plugin_payload_source(market / "plugins")
        manifest_path = market / ".agents" / "plugins" / "marketplace.json"
        write_json_atomic(manifest_path, _merged_marketplace_manifest({}, marketplace_profile))
        added_market = False
        added_plugin = False
        try:
            _run_codex(["plugin", "marketplace", "add", str(market)], home_override=isolated_home)
            added_market = True
            _run_codex(["plugin", "add", "%s@%s" % (PACKAGE, MARKETPLACE)], home_override=isolated_home)
            added_plugin = True
            result = _run_codex(["plugin", "list", "--json"], home_override=isolated_home)
            try:
                payload = json.loads(result.stdout or "")
                normalized = normalize_plugin_list(
                    payload, PACKAGE, MARKETPLACE, VERSION, json_profile,
                )
            except (json.JSONDecodeError, CompatibilityError) as exc:
                raise InstallError("隔离 Plugin 读回契约失败（期望 version=%s）: %s" % (VERSION, exc)) from exc
            if normalized is None:
                raise InstallError("隔离 Plugin 读回未发现目标 Plugin")
            return {
                "status": "ISOLATED_PLUGIN_PASS",
                "normalized_digest": canonical_digest(normalized),
            }
        finally:
            if added_plugin:
                _run_codex(
                    ["plugin", "remove", "%s@%s" % (PACKAGE, MARKETPLACE)],
                    check=False, home_override=isolated_home,
                )
            if added_market:
                _run_codex(
                    ["plugin", "marketplace", "remove", MARKETPLACE],
                    check=False, home_override=isolated_home,
                )


def _require_plugin_host() -> Dict[str, Any]:
    """中文：宿主无法证明能力时，在修改文件前失败关闭。

    English: Fail closed before changing files when the host cannot prove required capabilities.
    """
    profile = _probe_plugin_host()
    if not profile["version_ok"]:
        raise InstallError("Plugin 模式仅支持已验证的 Codex CLI %s；当前: %s" %
                           (", ".join(SUPPORTED_CODEX_VERSIONS),
                            profile["codex_version_output"] or "未知"))
    try:
        version_profile = profile_for_version(COMPATIBILITY_REGISTRY, str(profile["codex_version"]))
    except CompatibilityError as exc:
        raise InstallError("Plugin 宿主兼容档案无效，拒绝静态 async Hook 安装") from exc
    if not _native_async_user_prompt_submit_supported(version_profile):
        raise InstallError("当前 Codex 版本缺少已验证的 UserPromptSubmit async 能力，拒绝 Plugin 安装")
    if not _native_apply_patch_operation_supported(version_profile):
        raise InstallError("当前 Codex 版本缺少已验证的 apply_patch Pre/Post 能力，拒绝 Plugin 安装")
    if not profile["version_contract_ok"] or profile["command_contract_errors"]:
        raise InstallError(
            "Codex CLI 版本或 Plugin 子命令摘要与冻结兼容注册表不一致，拒绝安装: %s" %
            (profile["command_contract_errors"] or ["version_output"]),
        )
    if not profile["plugin_list_json"]:
        if not _legacy_marketplace_repairable():
            raise InstallError("codex plugin list --json schema 未知，拒绝 Plugin 安装")
        profile["legacy_marketplace_repair"] = True
        profile["ok"] = profile["version_ok"] and profile["version_contract_ok"] and not profile["command_contract_errors"] and all(
            item["ok"] for item in profile["commands"].values()
        )
    if not all(item["ok"] for item in profile["commands"].values()):
        raise InstallError("Codex Plugin 子命令能力不完整，拒绝安装: %s" % profile["commands"])
    profile["isolated_preflight"] = _isolated_plugin_preflight(profile)
    return profile


def validate_user_install_target() -> None:
    ch = codex_home()
    # 中文：防止误把源码或安装包目录当成 CODEX_HOME 后发生自覆盖。
    # English: Prevent self-overwrite when the source or package directory is mistaken for CODEX_HOME.
    source_root = ROOT.absolute()
    try:
        ch.relative_to(source_root)
        raise InstallError("危险目录：CODEX_HOME 位于 V6 源码/安装包目录内，拒绝自覆盖")
    except ValueError:
        pass


def install_user(mode: str, dry_run: bool, force: bool) -> None:
    validate_user_install_target()
    ch = codex_home(); sh = user_skills_home(); home = Path.home().absolute()
    current_skills = skill_names()
    deprecated_skills = deprecated_skill_names()
    old_base_state = _base_state() if mode == "plugin" else {}
    reject_link_ancestors(ch); reject_link_ancestors(home / ".agents")
    targets: List[Tuple[str, Path]] = [
        ("global", ch / "AGENTS.md"),
        ("install-state", state_path("user")),
        ("project-tool", ch / "tools" / "cp-runtime.py"),
        ("evolution-tool", ch / "tools" / "evolution.py"),
    ]
    targets.extend(("agent:" + p.name, ch / "agents" / p.name) for p in agent_files())
    legacy_targets = [("deprecated-skill:" + n, sh / n) for n in deprecated_skills]
    for _label, target in legacy_targets:
        ensure_inside(target, sh)
    targets.extend(legacy_targets)
    if mode == "standalone":
        current_skill_targets = [("skill:" + n, sh / n) for n in current_skills]
        for _label, target in current_skill_targets:
            ensure_inside(target, sh)
        targets.extend(current_skill_targets)
    else:
        targets.extend([
            ("plugin-payload", plugin_marketplace_payload()),
            ("marketplace-manifest", plugin_marketplace_manifest()),
            ("plugin-cache", plugin_cache_root()),
        ])
        if old_base_state:
            targets.append(("base-state", base_state_path()))
    # 中文：增强运行时始终是账户级受管组件；基础 Plugin 自身不加载它。
    # English: Enhancement runtime is always an account-managed component; the base Plugin itself never loads it.
    targets.extend([("runtime", ch / "runtime" / "cp_runtime"), ("hook-script", ch / "cp-assistant-hooks" / "cp_hook.py"),
                    ("gate-worker", ch / "cp-assistant-hooks" / "cp_gate.py"), ("hooks-json", ch / "hooks.json")])
    for _label, target in targets:
        reject_link_ancestors(target.parent)
    old_state = load_json(state_path("user"), {}) or {}
    migrated_old_state = migrate_state_to_v3(old_state, "user", mode)
    preference_migration = capability_preference_migration(old_state)
    if dry_run:
        print(json.dumps({"scope":"user","mode":mode,"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_schema":old_state.get("schema_version"),
                          "state_migration":"legacy-to-v3" if old_state.get("schema_version") in {1, 2} else "none",
                          "backup_required":True,"targets":[str(x[1]) for x in targets],
                          "preference_migration":preference_migration,
                          "base_upgrade":bool(old_base_state),
                          "unknown_marketplace_entries_preserved":mode == "plugin"}, ensure_ascii=False, indent=2)); return
    _require_no_live_transaction("user")
    if old_state and str(old_state.get("mode") or mode) != mode and not force:
        raise InstallError("当前已安装 mode=%s；Plugin/standalone 模式切换默认拒绝，请先卸载或使用 --force" % old_state.get("mode"))
    capability_profile: Dict[str, Any] = {}
    if mode == "plugin":
        capability_profile = _require_plugin_host()
        payload_report(ROOT)
    journal = _new_journal("user", mode, None, targets)
    _journal_write(journal, "PREPARED")
    backup = backup_root("user"); _io_path(backup).mkdir(parents=True, exist_ok=False)
    journal["backup"] = str(backup)
    records: List[Dict[str, Any]] = []
    previous_plugin_active = False
    previous_plugin_detail = ""
    previous_base_active = _base_plugin_active() if old_base_state and _codex_available() else False
    previous_market_exists = _io_path(plugin_marketplace_root()).exists() if mode == "plugin" else False
    if mode == "plugin" and _codex_available():
        try:
            previous_plugin_active, previous_plugin_detail = _plugin_activation_status()
        except Exception:
            previous_plugin_active = False
    try:
        for label, target in targets:
            _recheck_target(target, "user")
            records.append(backup_target(target, backup, label))
        journal["records"] = records
        previous_version = ""
        if previous_plugin_detail.startswith("{"):
            try:
                previous_version = str(json.loads(previous_plugin_detail).get("version") or "")
            except json.JSONDecodeError:
                previous_version = ""
        previous_cache = plugin_cache_root(previous_version) if previous_version else None
        journal["previous_plugin_state"] = {
            "active": previous_plugin_active,
            "marketplace_exists": previous_market_exists,
            "version": previous_version,
            "cache_path": str(previous_cache) if previous_cache else "",
            "cache_tree_sha256": tree_sha256(previous_cache) if previous_cache and previous_cache.is_dir() else "",
            "base_active": previous_base_active,
            "base_market_root": old_base_state.get("market_root") if old_base_state else "",
        }
        _journal_write(journal, "BACKED_UP")
        _journal_write(journal, "APPLYING")
        # 中文：更新全局受管区块。
        # English: Update the global managed block.
        gp = ch / "AGENTS.md"; _io_path(gp.parent).mkdir(parents=True, exist_ok=True)
        io_gp = _io_path(gp)
        existing = io_gp.read_text(encoding="utf-8-sig") if io_gp.exists() else ""
        text_atomic(gp, managed_global_text(existing))
        _record_applied(journal, "global", gp)
        # 中文：安装 Reviewer Agent 定义。
        # English: Install Reviewer Agent definitions.
        for src in agent_files():
            dst = ch / "agents" / src.name; copy_atomic(src, dst); _record_applied(journal, "agent:" + src.name, dst)
        for name in deprecated_skills:
            dst = sh / name
            if _io_path(dst).exists() or _io_path(dst).is_symlink():
                remove_path(dst)
            _record_applied(journal, "deprecated-skill:" + name, dst)
        for label, script_name in (("project-tool", "cp-runtime.py"), ("evolution-tool", "evolution.py")):
            dst = ch / "tools" / script_name
            copy_atomic(ROOT / "scripts" / script_name, dst)
            _record_applied(journal, label, dst)
        if mode == "standalone":
            for name in current_skills:
                dst = sh / name; copy_atomic(ROOT / "skills" / name, dst); _record_applied(journal, "skill:" + name, dst)
        # 中文：Plugin 模式由基础 Plugin 唯一加载 Skills；安装器只接入按需增强运行时。
        # English: In Plugin mode, only the base Plugin loads Skills; this installer adds the optional enhancement runtime.
        if mode in {"standalone", "plugin"}:
            dst = ch / "runtime" / "cp_runtime"; copy_atomic(ROOT / "runtime" / "cp_runtime", dst); _record_applied(journal, "runtime", dst)
            dst = ch / "cp-assistant-hooks" / "cp_hook.py"; copy_atomic(ROOT / "hooks" / "cp_hook.py", dst); _record_applied(journal, "hook-script", dst)
            dst = ch / "cp-assistant-hooks" / "cp_gate.py"; copy_atomic(ROOT / "hooks" / "cp_gate.py", dst); _record_applied(journal, "gate-worker", dst)
            merge_hooks(
                ch / "hooks.json", ch / "cp-assistant-hooks" / "cp_hook.py",
                _standalone_hook_profile(),
            )
            _record_applied(journal, "hooks-json", ch / "hooks.json")
        if mode == "plugin":
            market = plugin_marketplace_root()
            with tempfile.TemporaryDirectory(prefix="cp-v6-market-") as td:
                temporary_root = Path(td)
                src = plugin_payload_source(temporary_root / "payload")
                payload_report(src)
                payload_target = plugin_marketplace_payload()
                _record_mutation_intent(journal, "plugin-payload", payload_target, tree_sha256(src))
                if os.environ.get("CP_ASSISTANT_TEST_CRASH_PLUGIN_MARKETPLACE_STAGE") == "BEFORE_REPLACE":
                    journal["crash_injected"] = True
                    write_json_atomic(Path(journal["journal_path"]), journal)
                    raise InstallError("测试 Marketplace 替换前崩溃注入；请执行 doctor --recover")
                copy_atomic(src, payload_target)
                payload_report(payload_target)
                _record_applied(journal, "plugin-payload", payload_target)
                marketplace_path = plugin_marketplace_manifest()
                host_version_profile = profile_for_version(
                    COMPATIBILITY_REGISTRY, str(capability_profile["codex_version"]),
                )
                marketplace_profile = COMPATIBILITY_REGISTRY["profiles"]["marketplace"][
                    host_version_profile["marketplace_profile"]
                ]
                marketplace = _merged_marketplace_manifest(
                    load_json(marketplace_path, {}), marketplace_profile,
                )
                with tempfile.TemporaryDirectory(prefix="cp-v6-manifest-") as md:
                    prepared_manifest = Path(md) / "marketplace.json"
                    write_json_atomic(prepared_manifest, marketplace)
                    _record_mutation_intent(journal, "marketplace-manifest", marketplace_path,
                                            tree_sha256(prepared_manifest))
                    copy_atomic(prepared_manifest, marketplace_path)
                _record_applied(journal, "marketplace-manifest", marketplace_path)
                if os.environ.get("CP_ASSISTANT_TEST_CRASH_PLUGIN_MARKETPLACE_STAGE") == "AFTER_REPLACE":
                    journal["crash_injected"] = True
                    write_json_atomic(Path(journal["journal_path"]), journal)
                    raise InstallError("测试 Marketplace 替换后崩溃注入；请执行 doctor --recover")
                _hard_crash("MARKETPLACE:AFTER_REPLACE")
        if mode == "plugin":
            if old_base_state:
                _deactivate_base_plugin()
                _remove_base_marketplace()
            _journal_write(journal, "ACTIVATING")
            pre_activation_profile = _probe_plugin_host()
            same_host = (
                _host_identity_without_plugin_list(pre_activation_profile)
                == _host_identity_without_plugin_list(capability_profile)
                if capability_profile.get("legacy_marketplace_repair")
                else _host_binding(pre_activation_profile) == _host_binding(capability_profile)
            )
            pre_activation_ok = (
                pre_activation_profile.get("version_ok")
                and all(item["ok"] for item in pre_activation_profile["commands"].values())
                and (
                    pre_activation_profile.get("plugin_list_json")
                    or capability_profile.get("legacy_marketplace_repair")
                )
            )
            if not pre_activation_ok or not same_host:
                raise InstallError("安装事务期间 Codex 宿主发生变化，拒绝激活")
            _record_mutation_intent(journal, "plugin-cache", plugin_cache_root(),
                                    tree_sha256(plugin_marketplace_payload()))
            _activate_plugin(plugin_marketplace_root())
            _hard_crash("PLUGIN:AFTER_ADD")
            active, detail = _plugin_activation_status(VERSION)
            if not active:
                raise InstallError("Plugin 注册读回未达到 installed=true、enabled=true、version=%s: %s" % (VERSION, detail))
            post_activation_profile = _probe_plugin_host()
            if not post_activation_profile.get("ok") or (
                _host_identity_without_plugin_list(post_activation_profile)
                != _host_identity_without_plugin_list(pre_activation_profile)
            ):
                raise InstallError("Plugin 激活后宿主能力读回发生变化")
            cache_report = payload_report(plugin_cache_root())
            journal["cache_payload"] = cache_report
            _record_applied(journal, "plugin-cache", plugin_cache_root())
            _hard_crash("PLUGIN:AFTER_CACHE_VERIFY")
            if old_base_state:
                _io_path(base_state_path()).unlink(missing_ok=True)
                _record_applied(journal, "base-state", base_state_path())
        else:
            cache_report = None
        managed = {str(path): tree_sha256(path) for _label, path in targets if _io_path(path).exists() and _label not in {"global", "hooks-json", "install-state"}}
        global_hash = managed_global_sha256(gp)
        if not re.fullmatch(r"[0-9a-f]{64}", global_hash):
            raise InstallError("全局 AGENTS 受管区块无法唯一核验，拒绝提交安装状态")
        managed[str(gp)] = global_hash
        state = dict(migrated_old_state)
        state.update({"schema_version":3,"package":PACKAGE,"version":VERSION,"scope":"user","mode":mode,
                      "installed_at":time.time(),"backup":str(backup),"managed_hashes":managed,
                      "previous_backup":old_state.get("backup"),
                      "capability_profile":_host_binding(capability_profile) if mode == "plugin" else {},
                      "preference_migration":preference_migration,
                      "components":{
                          "base":{"status":"PLUGIN_MANAGED" if mode == "plugin" else "STANDALONE_SKILLS",
                                  "skills":current_skills},
                          "enhancement":{"status":"MANAGED",
                                         "runtime":str(ch / "runtime" / "cp_runtime"),
                                         "hooks":str(ch / "hooks.json")},
                      }})
        if mode == "plugin":
            source_report = payload_report(ROOT)
            marketplace_report = payload_report(plugin_marketplace_payload())
            state["payload_identity"] = {"manifest_digest":source_report["payload_digest"],
                                         "marketplace_digest":marketplace_report["payload_digest"],
                                         "cache_digest":cache_report["payload_digest"] if cache_report else None,
                                         "file_count":source_report["file_count"]}
            state["compatibility_status"] = "HOST_COMPATIBLE"
            state["compatibility_snapshot"] = _compatibility_snapshot(
                post_activation_profile, source_report["payload_digest"], detail,
            )
            # 中文：V7 SessionEnd 仅入队签名任务；提交安装前初始化主机绑定密钥环，
            # 中文：同时保留既有 V6.5 密钥和全部 RETIRED 验证历史。
            # English: V7 SessionEnd only enqueues a signed job; initialize the host-bound
            # English: keyring before commit while preserving V6.5 keys and RETIRED history.
            init_keyring()
            state["integrity_keyring"] = verify_keyring()
        else:
            state["compatibility_status"] = "STANDALONE_NOT_APPLICABLE"
            state.pop("compatibility_snapshot", None)
        write_json_atomic(state_path("user"), state)
        _record_applied(journal, "install-state", state_path("user"))
        _hard_crash("PLUGIN:AFTER_STATE_WRITE")
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"user","mode":mode})
        journal["applied_hashes"].update(managed)
        _journal_write(journal, "COMMITTED")
        _finish_journal(journal)
    except Exception as exc:
        journal["errors"].append(str(exc))
        if journal.get("crash_injected"):
            _archive_final_journal(journal)
            raise
        # 中文：安装事务失败时，撤销本次 Plugin 注册并恢复文件与旧状态，再尽力恢复升级前 Plugin。
        # English: On transaction failure, undo Plugin registration, restore files/state, then restore the prior Plugin.
        _journal_write(journal, "ROLLBACK_STARTED")
        if mode == "plugin" and _codex_available():
            try:
                _deactivate_plugin(check=False)
            except Exception as rollback_exc:
                journal["rollback_errors"].append("plugin deactivate: %s" % rollback_exc)
        for record in reversed(records):
            target = Path(record["target"])
            try:
                _recheck_target(target, "user")
                if not _target_owned(record, journal):
                    raise InstallError("目标已发生未知漂移，保留: %s" % target)
                previous = backup / record["backup_relative"] if record.get("existed") else None
                if target.name == "hooks.json":
                    restore_managed_hooks(target, previous); continue
                if target.name == "AGENTS.md":
                    restore_global_agents(target, previous); continue
                io_target = _io_path(target)
                if io_target.exists() or io_target.is_symlink(): remove_path(target)
                if record.get("existed"):
                    src = backup / record["backup_relative"]
                    copy_atomic(src, target)
            except Exception as rollback_exc:
                journal["rollback_errors"].append("restore %s: %s" % (target, rollback_exc))
        if mode == "plugin" and _codex_available():
            if not previous_market_exists:
                try:
                    _remove_marketplace(check=False)
                    _remove_empty_marketplace_dirs()
                except Exception as rollback_exc:
                    journal["rollback_errors"].append("marketplace deactivate: %s" % rollback_exc)
            if previous_plugin_active and _io_path(plugin_marketplace_root()).exists():
                try:
                    _activate_plugin(plugin_marketplace_root())
                    _verify_restored_plugin(journal.get("previous_plugin_state") or {})
                except Exception as rollback_exc:
                    journal["rollback_errors"].append("plugin reactivate: %s" % rollback_exc)
            if journal.get("previous_plugin_state", {}).get("base_active") and _io_path(base_marketplace_root()).exists():
                try:
                    _run_codex(["plugin", "marketplace", "add", str(base_marketplace_root())])
                    _run_codex(["plugin", "add", "%s@%s" % (PACKAGE, BASE_MARKETPLACE)])
                except Exception as rollback_exc:
                    journal["rollback_errors"].append("base plugin reactivate: %s" % rollback_exc)
        _journal_write(journal, "RECOVERY_REQUIRED" if journal["rollback_errors"] else "ROLLED_BACK")
        if not journal["rollback_errors"]:
            _finish_journal(journal)
        else:
            _archive_final_journal(journal)
        if journal["rollback_errors"]:
            raise InstallError("安装失败且回滚不完整；请执行 doctor --recover：%s" % "; ".join(journal["rollback_errors"])) from exc
        raise
    print("[OK] V%s 账户级安装完成，mode=%s" % (VERSION, mode))
    if mode == "plugin":
        print("[OK] Codex Marketplace 已注册，Plugin 已执行 codex plugin add")


def install_repo(repo_path: str, dry_run: bool) -> None:
    repo = git_root(Path(repo_path))
    root = repo / ".agents" / "skills"
    reject_link_ancestors(root.parent, repo)
    targets = ([("deprecated-skill:" + n, root / n) for n in deprecated_skill_names()] +
               [("skill:" + n, root / n) for n in skill_names()] +
               [("install-state", state_path("repo", repo))])
    for _label, target in targets:
        ensure_inside(target, repo); reject_link_ancestors(target.parent, repo)
    old_state = load_json(state_path("repo", repo), {}) or {}
    migrated_old_state = migrate_state_to_v3(old_state, "repo", "standalone")
    preference_migration = capability_preference_migration(old_state)
    if dry_run:
        print(json.dumps({"scope":"repo","repo":str(repo),"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_migration":"legacy-to-v3" if old_state.get("schema_version") in {1, 2} else "none",
                          "preference_migration":preference_migration,
                          "targets":[str(t) for _,t in targets]}, ensure_ascii=False, indent=2)); return
    _require_no_live_transaction("repo", repo)
    journal = _new_journal("repo", "standalone", repo, targets)
    _journal_write(journal, "PREPARED")
    backup = backup_root("repo", repo); _io_path(backup).mkdir(parents=True, exist_ok=False)
    journal["backup"] = str(backup)
    records = []
    try:
        for label, target in targets:
            _recheck_target(target, "repo", repo)
            records.append(backup_target(target, backup, label))
        journal["records"] = records
        _journal_write(journal, "BACKED_UP")
        _journal_write(journal, "APPLYING")
        for name in deprecated_skill_names():
            dst = root / name
            if _io_path(dst).exists() or _io_path(dst).is_symlink():
                remove_path(dst)
            _record_applied(journal, "deprecated-skill:" + name, dst)
        for name in skill_names():
            dst = root / name; copy_atomic(ROOT / "skills" / name, dst); _record_applied(journal, "skill:" + name, dst)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"repo"})
        managed = {str(t):tree_sha256(t) for label,t in targets if label != "install-state"}
        state = dict(migrated_old_state)
        state.update({"schema_version":3,"package":PACKAGE,"version":VERSION,"scope":"repo","mode":"standalone",
                      "repo":str(repo),"backup":str(backup),"previous_backup":old_state.get("backup"),
                      "managed_hashes":managed,"compatibility_status":"STANDALONE_NOT_APPLICABLE"})
        state["preference_migration"] = preference_migration
        state.pop("compatibility_snapshot", None)
        write_json_atomic(state_path("repo", repo), state)
        _record_applied(journal, "install-state", state_path("repo", repo))
        journal["applied_hashes"].update(managed)
        _journal_write(journal, "COMMITTED"); _finish_journal(journal)
    except Exception as exc:
        journal["errors"].append(str(exc))
        if journal.get("crash_injected"):
            _archive_final_journal(journal); raise
        _journal_write(journal, "ROLLBACK_STARTED")
        for record in reversed(records):
            target=Path(record["target"])
            try:
                _recheck_target(target, "repo", repo)
                if not _target_owned(record, journal):
                    raise InstallError("目标已发生未知漂移，保留: %s" % target)
                io_target = _io_path(target)
                if io_target.exists() or io_target.is_symlink(): remove_path(target)
                if record.get("existed"): copy_atomic(backup / record["backup_relative"], target)
            except Exception as rollback_exc:
                journal["rollback_errors"].append("%s: %s" % (target, rollback_exc))
        _journal_write(journal, "RECOVERY_REQUIRED" if journal["rollback_errors"] else "ROLLED_BACK")
        if not journal["rollback_errors"]: _finish_journal(journal)
        else: _archive_final_journal(journal)
        if journal["rollback_errors"]:
            raise InstallError("仓库安装回滚不完整；请执行 doctor --recover") from exc
        raise
    print("[OK] V%s 仓库级 Skills 安装完成: %s" % (VERSION, repo))


def verify(scope: str, mode: str, repo_path: Optional[str]) -> None:
    errors: List[str] = []
    if scope == "repo":
        repo = git_root(Path(repo_path or ".")); root = repo / ".agents" / "skills"
        for name in deprecated_skill_names():
            if _io_path(root / name).exists(): errors.append("遗留旧 Skill %s" % (root / name))
        for name in skill_names():
            dst=root/name; src=ROOT/"skills"/name
            if not _io_path(dst).is_dir(): errors.append("缺少 %s" % dst)
            elif tree_sha256(dst)!=tree_sha256(src): errors.append("内容漂移 %s" % dst)
    else:
        ch=codex_home()
        if mode == "standalone":
            for name in deprecated_skill_names():
                if _io_path(user_skills_home()/name).exists(): errors.append("遗留旧 Skill %s" % name)
            for name in skill_names():
                dst=user_skills_home()/name; src=ROOT/"skills"/name
                if not _io_path(dst).is_dir(): errors.append("缺少 Skill %s" % name)
                elif tree_sha256(dst)!=tree_sha256(src): errors.append("Skill 漂移 %s" % name)
            if not _io_path(ch/"cp-assistant-hooks"/"cp_hook.py").is_file(): errors.append("缺少 standalone Hook")
            if not _io_path(ch/"cp-assistant-hooks"/"cp_gate.py").is_file(): errors.append("缺少 standalone 流程门禁 Worker")
        else:
            market = plugin_marketplace_root()
            plugin=market/"plugins"/PACKAGE
            for name in deprecated_skill_names():
                if _io_path(plugin/"skills"/name).exists(): errors.append("Plugin 遗留旧 Skill %s" % name)
            if not _io_path(market/".agents"/"plugins"/"marketplace.json").is_file(): errors.append("缺少 Codex Marketplace manifest")
            if not _io_path(plugin/".codex-plugin"/"plugin.json").is_file(): errors.append("缺少 Plugin")
            base_manifest = load_json(plugin/".codex-plugin"/"plugin.json", {}) or {}
            if base_manifest.get("skills") != "./skills/": errors.append("基础 Plugin Skill 入口无效")
            base_hooks = load_json(plugin/"hooks"/"hooks.json", {}) or {}
            if base_hooks.get("hooks") != {}: errors.append("基础 Plugin 不得直接注册增强 Hook")
            active, detail = _plugin_activation_status(VERSION)
            if not active: errors.append("Plugin 未被 Codex 实际安装并启用: %s" % detail)
            try:
                source_report = payload_report(ROOT)
                market_report = payload_report(plugin)
                cache_report = payload_report(plugin_cache_root())
                digests = {source_report["payload_digest"], market_report["payload_digest"], cache_report["payload_digest"]}
                if len(digests) != 1:
                    errors.append("ZIP 源/Marketplace/cache payload digest 不一致")
                state = migrate_state_to_v3(load_json(state_path("user"), {}) or {}, "user", mode)
                identity = state.get("payload_identity") or {}
                if state.get("version") != VERSION or state.get("schema_version") != 3:
                    errors.append("安装状态不是 V%s schema 3" % VERSION)
                if any(identity.get(key) != source_report["payload_digest"]
                       for key in ("manifest_digest", "marketplace_digest", "cache_digest")):
                    errors.append("安装状态 payload 身份读回不一致")
                host_status = _host_compatibility_status(state)
                if not host_status.get("compatible"):
                    errors.append("Codex 宿主兼容状态: %s" % host_status.get("status"))
            except InstallError as exc:
                errors.append(str(exc))
            try:
                verify_keyring()
            except Exception as exc:
                errors.append("完整性 keyring 不可用: %s" % exc)
            if not _io_path(ch/"cp-assistant-hooks"/"cp_hook.py").is_file(): errors.append("缺少增强 Hook")
            if not _io_path(ch/"cp-assistant-hooks"/"cp_gate.py").is_file(): errors.append("缺少增强流程门禁 Worker")
            else:
                errors.extend(_managed_hook_errors(
                    ch / "hooks.json", ch / "cp-assistant-hooks" / "cp_hook.py",
                    _standalone_hook_profile(),
                ))
        for script_name in ("cp-runtime.py", "evolution.py"):
            dst = ch / "tools" / script_name
            src = ROOT / "scripts" / script_name
            if not _io_path(dst).is_file():
                errors.append("缺少账户工具 %s" % script_name)
            elif tree_sha256(dst) != tree_sha256(src):
                errors.append("账户工具漂移 %s" % script_name)
        for src in agent_files():
            if not _io_path(ch/"agents"/src.name).is_file(): errors.append("缺少 Reviewer %s" % src.name)
        io_agents = _io_path(ch/"AGENTS.md")
        text=io_agents.read_text(encoding="utf-8-sig") if io_agents.is_file() else ""
        if BEGIN not in text or END not in text: errors.append("缺少全局 AGENTS 受管区块")
    if errors:
        for item in errors: print("[FAIL]",item)
        raise SystemExit(1)
    print("[OK] V%s 安装验证通过 scope=%s mode=%s" % (VERSION, scope, mode))


def uninstall(scope: str, mode: str, repo_path: Optional[str], force: bool, dry_run: bool) -> None:
    repo = git_root(Path(repo_path or ".")) if scope == "repo" else None
    sp = state_path(scope, repo)
    state = load_json(sp, {}) or {}
    if not state:
        if dry_run:
            preview = inventory(scope, mode, repo_path)
            preview.update({"operation":"uninstall-preview", "will_delete":[],
                            "real_uninstall":"REFUSED_WITHOUT_STATE", "delete_authorized":False})
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            return
        raise InstallError("未找到 V6 安装状态文件；为避免误删未知资产，拒绝无状态卸载")
    installed_mode = str(state.get("mode") or mode)
    hashes = state.get("managed_hashes") or {}
    drift = []
    for raw, expected in hashes.items():
        path=Path(raw)
        if _io_path(path).exists() and str(expected) not in {"", "missing"} and tree_sha256(path)!=expected:
            # 中文：global 保存的是源区块哈希，整文件天然不同，因此不做整文件漂移比较。
            # English: The global record stores a source-block hash, so whole-file drift comparison does not apply.
            if path.name != "AGENTS.md": drift.append(str(path))
    if drift and not force:
        raise InstallError("检测到外部修改，拒绝覆盖式卸载；确认后使用 --force：%s" % drift)
    backup = Path(state.get("backup") or "")
    manifest_data = load_json(backup / "backup-manifest.json", {}) or {}
    records = manifest_data.get("records") or []
    previous_market_records = [r for r in records if r.get("label") in {"plugin-payload", "marketplace-manifest", "plugin-marketplace"}]
    previous_state_record = next((r for r in records if r.get("label") == "install-state"), None)
    previous_state = {}
    if previous_state_record and previous_state_record.get("existed") and previous_state_record.get("backup_relative"):
        previous_state = load_json(backup / previous_state_record["backup_relative"], {}) or {}
    if dry_run:
        print(json.dumps({"restore_backup":str(backup),"records":records,"installed_mode":installed_mode},ensure_ascii=False,indent=2)); return
    _require_no_live_transaction(scope, repo)
    transaction_targets = [(str(r.get("label") or "managed"), Path(r["target"])) for r in records]
    journal = _new_journal(scope, installed_mode, repo, transaction_targets)
    journal["operation"] = "uninstall"
    _journal_write(journal, "PREPARED")
    undo_backup = backup_root(scope, repo); _io_path(undo_backup).mkdir(parents=True, exist_ok=False)
    journal["backup"] = str(undo_backup)
    undo_records: List[Dict[str, Any]] = []
    for label, target in transaction_targets:
        _recheck_target(target, scope, repo)
        undo_records.append(backup_target(target, undo_backup, label))
    journal["records"] = undo_records
    journal["applied_hashes"] = {str(r["target"]): tree_sha256(Path(r["target"]))
                                 for r in undo_records if _io_path(Path(r["target"])).exists()}
    if installed_mode == "plugin":
        active = False
        active_detail = ""
        if _codex_available():
            active, active_detail = _plugin_activation_status(VERSION)
        active_version = ""
        if active_detail.startswith("{"):
            try:
                active_version = str(json.loads(active_detail).get("version") or "")
            except json.JSONDecodeError:
                active_version = ""
        active_cache = plugin_cache_root(active_version) if active_version else None
        journal["previous_plugin_state"] = {
            "active": active, "marketplace_exists": _io_path(plugin_marketplace_root()).exists(),
            "version": active_version, "cache_path": str(active_cache) if active_cache else "",
            "cache_tree_sha256": tree_sha256(active_cache) if active_cache and active_cache.is_dir() else "",
        }
    _journal_write(journal, "BACKED_UP")
    _journal_write(journal, "APPLYING")
    if installed_mode == "plugin":
        if _codex_available():
            try:
                _deactivate_plugin(check=not force)
                if not any(record.get("existed") for record in previous_market_records):
                    _remove_marketplace(check=not force)
                if os.environ.get("CP_ASSISTANT_TEST_CRASH_AFTER_PLUGIN_DEACTIVATE"):
                    journal["crash_injected"] = True
                    write_json_atomic(Path(journal["journal_path"]), journal)
                    raise InstallError("测试 Plugin 注销后崩溃注入；请执行 doctor --recover")
            except InstallError:
                if not force:
                    raise
                print("[WARN] --force：Codex Plugin/Marketplace 注册状态未能完整清理，继续恢复受管文件")
        elif not force:
            raise InstallError("当前找不到 codex CLI，无法安全注销已安装 Plugin；可在确认后使用 --force 仅恢复受管文件")
        else:
            print("[WARN] --force：找不到 codex CLI，仅恢复受管文件；Plugin 缓存/配置可能仍需由 Codex 清理")
    for record in reversed(records):
        target=Path(record["target"])
        _recheck_target(target, scope, repo)
        previous = backup / record["backup_relative"] if record.get("existed") and record.get("backup_relative") else None
        if target.name == "hooks.json" and scope == "user":
            restore_managed_hooks(target, previous)
            _record_applied(journal, str(record.get("label") or "hooks-json"), target)
            continue
        if target.name == "AGENTS.md" and scope == "user":
            restore_global_agents(target, previous)
            _record_applied(journal, str(record.get("label") or "global"), target)
            continue
        io_target = _io_path(target)
        if io_target.exists() or io_target.is_symlink(): remove_path(target)
        if record.get("existed"):
            src=backup/record["backup_relative"]
            if tree_sha256(src)!=record.get("sha256"): raise InstallError("备份完整性失败: %s" % src)
            copy_atomic(src,target)
        _record_applied(journal, str(record.get("label") or "managed"), target)
    if installed_mode == "plugin" and not any(record.get("existed") for record in previous_market_records):
        _remove_empty_marketplace_dirs()
    # 中文：V7 将自身状态文件记为事务目标；若旧 V6 状态存在，恢复循环已将其还原，
    # 中文：否则必须确保当前状态文件不存在。
    # English: V7 records its state file as a transactional target; the restore loop reinstates
    # English: an older V6 state when present, otherwise no current state file may remain.
    if not previous_state_record:
        _io_path(sp).unlink(missing_ok=True)
    if installed_mode == "plugin" and previous_state.get("mode") == "plugin" and _codex_available() and _io_path(plugin_marketplace_root()).exists():
        try:
            _activate_plugin(plugin_marketplace_root())
            restored, detail = _plugin_activation_status(str(previous_state.get("version") or "") or None)
            if not restored:
                raise InstallError("旧 Plugin 版本读回失败: %s" % detail)
        except Exception as exc:
            if not force:
                raise InstallError("已恢复旧版文件，但旧 Plugin 重新激活失败: %s" % exc)
            print("[WARN] --force：旧版 Plugin 文件已恢复，但未能重新激活")
    if installed_mode == "plugin" and _io_path(base_state_path()).is_file() and _codex_available():
        try:
            _base_state()
            if not _io_path(base_marketplace_root()).is_dir():
                raise InstallError("基础 Marketplace 源目录缺失")
            _run_codex(["plugin", "marketplace", "add", str(base_marketplace_root())])
            _run_codex(["plugin", "add", "%s@%s" % (PACKAGE, BASE_MARKETPLACE)])
            if not _base_plugin_active():
                raise InstallError("基础 Plugin 重新激活读回失败")
        except Exception as exc:
            if not force:
                raise InstallError("已恢复基础安装文件，但基础 Plugin 重新激活失败: %s" % exc)
            print("[WARN] --force：基础安装文件已恢复，但未能重新激活")
    _journal_write(journal, "COMMITTED")
    _finish_journal(journal)
    print("[OK] V%s 已卸载并恢复安装前状态；项目上下文/观测数据未删除" % VERSION)


def _load_live_journal(scope: str, repo: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = transaction_path(scope, repo)
    if not _io_path(path).exists():
        return None
    try:
        data = load_json(path)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise InstallError("事务 journal 损坏，拒绝猜测恢复: %s" % path) from exc
    if not isinstance(data, dict) or data.get("schema_version") != JOURNAL_SCHEMA:
        raise InstallError("事务 journal schema 未知，拒绝恢复: %s" % path)
    if data.get("scope") != scope or data.get("stage") not in JOURNAL_STAGES:
        raise InstallError("事务 journal 内容未知或 scope 不匹配，拒绝恢复: %s" % path)
    return data


def recover_transaction(scope: str, repo_path: Optional[str] = None) -> None:
    repo = git_root(Path(repo_path or ".")) if scope == "repo" else None
    journal = _load_live_journal(scope, repo)
    if not journal:
        print("[OK] 未发现待恢复事务"); return
    path = Path(journal["journal_path"])
    if journal["stage"] == "COMMITTED":
        _archive_final_journal(journal); _io_path(path).unlink(missing_ok=True)
        print("[OK] 已归档并清理已提交事务 journal"); return
    if journal["stage"] in {"ROLLED_BACK"}:
        _archive_final_journal(journal); _io_path(path).unlink(missing_ok=True)
        print("[OK] 已归档并清理已回滚事务 journal"); return
    # 中文：PREPARED 在备份目录创建前持久化；此时尚未触碰受管目标，恢复只需归档并清理。
    # English: PREPARED is persisted before the backup exists; no managed target has been touched,
    # English: so recovery only archives and cleans up the journal.
    if journal["stage"] == "PREPARED" and not journal.get("backup"):
        _journal_write(journal, "ROLLED_BACK"); _finish_journal(journal)
        print("[OK] PREPARED 事务尚未写入受管目标，已安全清理"); return
    journal["rollback_errors"] = list(journal.get("rollback_errors") or [])
    _journal_write(journal, "ROLLBACK_STARTED")
    backup_value = journal.get("backup")
    backup = Path(str(backup_value)) if backup_value else None
    if backup is None or not backup.is_dir():
        journal["rollback_errors"].append("备份目录不存在: %s" % backup)
    for record in reversed(journal.get("records") or []):
        try:
            target = Path(record["target"]); _recheck_target(target, scope, repo)
            if not _target_owned(record, journal):
                raise InstallError("目标已发生未知漂移，保留: %s" % target)
            previous = backup / str(record.get("backup_relative") or "") if backup and record.get("existed") else None
            if target.name == "hooks.json" and scope == "user":
                restore_managed_hooks(target, previous); continue
            if target.name == "AGENTS.md" and scope == "user":
                restore_global_agents(target, previous); continue
            io_target = _io_path(target)
            if io_target.exists() or io_target.is_symlink(): remove_path(target)
            if record.get("existed"):
                assert backup is not None
                src = backup / str(record.get("backup_relative") or "")
                if not src.exists() or tree_sha256(src) != record.get("sha256"):
                    raise InstallError("备份完整性失败: %s" % src)
                copy_atomic(src, target)
        except Exception as exc:
            journal["rollback_errors"].append("%s: %s" % (record.get("target"), exc))
    if scope == "user" and journal.get("mode") == "plugin" and _codex_available():
        previous_plugin = journal.get("previous_plugin_state") or {}
        try:
            _deactivate_plugin(check=False)
            if not previous_plugin.get("marketplace_exists"):
                _remove_marketplace(check=False)
            if previous_plugin.get("active") and _io_path(plugin_marketplace_root()).exists():
                _activate_plugin(plugin_marketplace_root())
                _verify_restored_plugin(previous_plugin)
            if not previous_plugin.get("marketplace_exists"):
                _remove_empty_marketplace_dirs()
        except Exception as exc:
            journal["rollback_errors"].append("Plugin 恢复: %s" % exc)
    stage = "RECOVERY_REQUIRED" if journal["rollback_errors"] else "ROLLED_BACK"
    _journal_write(journal, stage)
    if stage == "RECOVERY_REQUIRED":
        raise InstallError("事务恢复未完成: %s" % "; ".join(journal["rollback_errors"]))
    _finish_journal(journal)
    print("[OK] 事务恢复完成")


def status_summary(data: Mapping[str, Any]) -> Dict[str, Any]:
    """中文：将安装事实投影为可行动状态，不删改完整 JSON 契约。

    English: Project installation facts into an actionable status without removing the full JSON contract.
    """
    ux = _ux_summary(data)
    return {
        "overall": ux["overall"],
        "available": ux["available"],
        "affected": ux["affected"],
        "cause": ux["cause"],
        "next_action": (ux.get("next_action_detail") or {}).get("display_command") or
                       (ux.get("next_action_detail") or {}).get("expected_result") or "可直接开始任务",
        "ux": ux,
    }


def _diagnostic_object(path: Path) -> Tuple[Dict[str, Any], Optional[str]]:
    """中文：诊断读取拒绝链接、超大文件与重复字段，不修复文件。

    English: Diagnostic reads reject links, oversized files, and duplicate keys without repair.
    """
    from cp_runtime.capability_store import bounded_read, safe_path, unique_json_object, CapabilityError
    try:
        checked = safe_path(path)
        try:
            checked.stat()
        except FileNotFoundError:
            return {}, None
        value = json.loads(bounded_read(path, 8 * 1024 * 1024).decode("utf-8-sig"),
                           object_pairs_hook=unique_json_object)
        if not isinstance(value, dict):
            return {}, "STATE_OBJECT_REQUIRED"
        return value, None
    except (OSError, ValueError, UnicodeError, CapabilityError):
        return {}, "STATE_UNREADABLE_OR_INVALID"


def _diagnostic_journal(scope: str, repo: Optional[Path]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """中文：诊断有界读取 journal，保留恢复器的格式合同且不执行恢复。

    English: Read journals within diagnostic bounds, retaining the recovery format without recovery writes.
    """
    value, error = _diagnostic_object(transaction_path(scope, repo))
    if error:
        return None, "TRANSACTION_UNREADABLE"
    if not value:
        try:
            return (None, "TRANSACTION_UNREADABLE") if _io_path(transaction_path(scope, repo)).exists() else (None, None)
        except (OSError, InstallError):
            return None, "TRANSACTION_UNREADABLE"
    if value.get("schema_version") != JOURNAL_SCHEMA or value.get("scope") != scope or value.get("stage") not in JOURNAL_STAGES:
        return None, "TRANSACTION_UNREADABLE"
    return value, None


def _diagnostic_base_files(skills_root: Path) -> List[str]:
    problems = []
    for name in skill_names():
        path = skills_root / name / "SKILL.md"
        try:
            reject_link_ancestors(path)
            if not _io_path(path).is_file():
                problems.append("BASE_SKILL_MISSING")
        except (OSError, InstallError):
            problems.append("BASE_SKILL_UNREADABLE_OR_UNSAFE")
    return sorted(set(problems))


def _diagnostic_facts_once(scope: str, mode: Optional[str], repo_path: Optional[str]) -> Dict[str, Any]:
    repo = None
    non_git = False
    if scope == "repo":
        try:
            repo = git_root(Path(repo_path or "."))
        except InstallError:
            non_git = True
    source_state_path = state_path(scope, repo) if not non_git else None
    state, state_error = _diagnostic_object(source_state_path) if source_state_path else ({}, None)
    state_read_error = state_error
    if state and (type(state.get("schema_version")) is not int or
                  state.get("schema_version") not in {1, 2, 3} or state.get("package") != PACKAGE):
        state_error = "INSTALLATION_STATE_IDENTITY_INVALID"
    for key in ("components", "managed_hashes", "payload_identity"):
        if key in state and not isinstance(state[key], dict):
            state_error = "INSTALLATION_STATE_FIELDS_INVALID"
    mode_error = _mode_error(state.get("mode"))
    selected_mode = mode if mode in {"plugin", "standalone"} else _normalized_mode(state.get("mode"))
    if state.get("mode") in {"plugin", "standalone"} and mode and mode != state["mode"]:
        mode_error = "REQUESTED_MODE_MISMATCH"
    base_state, base_error = _diagnostic_object(base_state_path()) if scope == "user" else ({}, None)
    base_read_error = base_error
    if base_state and (
            base_state.get("schema_version") != 1 or base_state.get("package") != PACKAGE
            or base_state.get("marketplace") != BASE_MARKETPLACE
            or Path(str(base_state.get("market_root", ""))) != base_marketplace_root()
            or base_state.get("status", "INSTALLED") not in {"INSTALLING", "INSTALLED", "RECOVERY_REQUIRED"}):
        base_error = "BASE_STATE_IDENTITY_INVALID"
    live = None
    transaction_error = None
    if not non_git:
        live, transaction_error = _diagnostic_journal(scope, repo)
    capability = None
    registrations: Dict[str, Any] = {"checked": False, "base": None, "enhancement": None}
    if scope == "user" and selected_mode == "plugin" and _codex_available():
        try:
            capability = _probe_plugin_host(timeout=5)
            registrations = capability.get("registrations") or registrations
        except (OSError, ValueError, InstallError, CompatibilityError, subprocess.TimeoutExpired):
            registrations["detail"] = "HOST_PROBE_UNAVAILABLE"
    base_record = registrations.get("base") or {}
    enhanced_record = registrations.get("enhancement") or {}
    base_registered = bool(base_record.get("installed") and base_record.get("enabled"))
    enhanced_registered = bool(enhanced_record.get("installed") and enhanced_record.get("enabled"))
    base_active = _base_capability_active(
        bool(registrations.get("checked")), selected_mode,
        base_state if not base_error else {}, state, enhanced_registered, base_registered,
    )
    component_errors: Dict[str, List[str]] = {"base": [], "enhancement": []}
    payload_reports = None
    installed_version = state.get("version") or base_record.get("version") or enhanced_record.get("version")
    if scope == "repo" and repo is not None and state:
        component_errors["base"] = _diagnostic_base_files(repo / ".agents" / "skills")
        base_active = not component_errors["base"]
    elif scope == "user" and selected_mode == "standalone":
        component_errors["base"] = _diagnostic_base_files(user_skills_home())
        base_active = bool(state) and not component_errors["base"]
    elif base_active:
        record = enhanced_record if enhanced_registered else base_record
        market = MARKETPLACE if enhanced_registered else BASE_MARKETPLACE
        version = str(record.get("version") or "")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            component_errors["base"] = ["BASE_VERSION_UNVERIFIED"]
        else:
            cache = codex_home() / "plugins" / "cache" / market / PACKAGE / version
            component_errors["base"] = _diagnostic_base_files(cache / "skills")
    components = state.get("components") if isinstance(state.get("components"), dict) else {}
    enhancement_selected = scope == "user" and bool(state)
    managed_hashes = state.get("managed_hashes") if isinstance(state.get("managed_hashes"), dict) else {}
    payload_identity = state.get("payload_identity") if isinstance(state.get("payload_identity"), dict) else {}
    if enhancement_selected:
        if enhanced_registered and state.get("version") != enhanced_record.get("version"):
            state_error = "INSTALLATION_VERSION_CONFLICT"
        for path in [
            codex_home() / "tools" / "cp-runtime.py", codex_home() / "tools" / "evolution.py",
            codex_home() / "cp-assistant-hooks" / "cp_hook.py",
            codex_home() / "cp-assistant-hooks" / "cp_gate.py",
            *[codex_home() / "agents" / item.name for item in agent_files()],
        ]:
            try:
                reject_link_ancestors(path)
                if not _io_path(path).is_file():
                    component_errors["enhancement"].append("ENHANCEMENT_FILE_MISSING")
            except (OSError, InstallError):
                component_errors["enhancement"].append("ENHANCEMENT_PATH_UNREADABLE_OR_UNSAFE")
        if selected_mode == "plugin" and isinstance(installed_version, str) and re.fullmatch(r"\d+\.\d+\.\d+", installed_version):
            cache = plugin_cache_root(installed_version)
            try:
                own_manifest = load_payload_manifest(cache / PAYLOAD_MANIFEST_NAME)
                payload = verify_payload(cache, own_manifest, package=PACKAGE, version=installed_version)
                payload_reports = {"source": None, "marketplace": None, "cache": payload}
                try:
                    payload_reports["source"] = payload_report(ROOT)
                except (OSError, ValueError, InstallError):
                    payload_reports["source"] = {"ok": False, "error": "SOURCE_PAYLOAD_UNVERIFIED"}
                marketplace = plugin_marketplace_payload()
                try:
                    market_manifest = load_payload_manifest(marketplace / PAYLOAD_MANIFEST_NAME)
                    payload_reports["marketplace"] = verify_payload(
                        marketplace, market_manifest, package=PACKAGE, version=installed_version)
                    if payload_identity.get("marketplace_digest") != payload_reports["marketplace"].get("payload_digest"):
                        component_errors["enhancement"].append("MARKETPLACE_PAYLOAD_IDENTITY_MISMATCH")
                except (OSError, ValueError, PayloadIntegrityError, InstallError):
                    payload_reports["marketplace"] = {"ok": False, "error": "MARKETPLACE_PAYLOAD_UNVERIFIED"}
                    component_errors["enhancement"].append("MARKETPLACE_PAYLOAD_UNVERIFIED")
                expected = payload_identity.get("cache_digest")
                if expected != payload.get("payload_digest"):
                    component_errors["enhancement"].append("INSTALLED_PAYLOAD_IDENTITY_MISMATCH")
            except (OSError, ValueError, PayloadIntegrityError, InstallError):
                component_errors["enhancement"].append("INSTALLED_PAYLOAD_UNVERIFIED")
        else:
            try:
                runtime = codex_home() / "runtime" / "cp_runtime"
                expected = managed_hashes.get(str(runtime))
                if not expected or tree_sha256(runtime) != expected:
                    component_errors["enhancement"].append("INSTALLED_RUNTIME_UNVERIFIED")
            except (OSError, InstallError):
                component_errors["enhancement"].append("INSTALLED_RUNTIME_UNVERIFIED")
    host = None
    if scope == "user" and selected_mode == "plugin" and enhancement_selected:
        if capability is not None:
            host = _host_compatibility_status(state, observed=capability)
        else:
            host = {"compatible": False, "status": "HOST_PROBE_UNAVAILABLE"}
    return {
        "package": PACKAGE, "version": VERSION, "scope": scope, "mode": selected_mode,
        "repo_path": str(repo) if repo else str(Path(repo_path or ".").absolute()) if scope == "repo" else None,
        "git_repository": not non_git if scope == "repo" else None,
        "state": state, "mode_error": mode_error, "state_error": state_error,
        "base_state": base_state, "base_state_error": base_error,
        "_read_errors": {"state": state_read_error, "base_state": base_read_error},
        "live_transaction": live, "transaction_error": transaction_error,
        "plugin_activation": {"active": enhanced_registered, "checked": registrations.get("checked", False)},
        "registrations": registrations,
        "base_activation": {"active": base_active,
                            "checked": registrations.get("checked", False) if selected_mode == "plugin" else True,
                            "detail": registrations.get("detail", "")},
        "duplicate_registration": base_registered and enhanced_registered,
        "host_compatibility": host, "capability_profile": capability,
        "installed_version": installed_version, "enhancement_selected": enhancement_selected,
        "component_errors": {key: sorted(set(value)) for key, value in component_errors.items()},
        "payload_identity": payload_reports, "skills": skill_names(), "reviewers": [item.name for item in agent_files()],
        "hooks": str(codex_home() / "hooks.json") if scope == "user" else None,
    }


def _diagnostic_facts(scope: str, mode: Optional[str], repo_path: Optional[str],
                      profile_path: Optional[str] = None) -> Dict[str, Any]:
    """中文：稳定采样后按显式项目/当前任务环境评估控制准备条件。

    English: Check sample stability and control prerequisites for an explicit project or current task environment.
    """
    for attempt in range(2):
        data = _diagnostic_facts_once(scope, mode, repo_path)
        stable = True
        paths = []
        if data.get("git_repository") is not False:
            paths.append((state_path(scope, Path(data["repo_path"]) if scope == "repo" else None),
                          data["state"], data["_read_errors"]["state"]))
        if scope == "user":
            paths.append((base_state_path(), data["base_state"], data["_read_errors"]["base_state"]))
        for path, captured, error in paths:
            value, current_error = _diagnostic_object(path)
            if value != captured or current_error != error:
                stable = False
        if data.get("git_repository") is not False:
            live, journal_error = _diagnostic_journal(scope, Path(data["repo_path"]) if scope == "repo" else None)
            if live != data["live_transaction"] or journal_error != data["transaction_error"]:
                stable = False
        if stable:
            break
    data.pop("_read_errors", None)
    if not stable:
        data["sample_error"] = "INSTALLATION_CHANGED_DURING_READ"
        data["base_activation"] = {"active": False, "checked": False, "detail": data["sample_error"]}
    controls: Dict[str, Any] = {}
    if profile_path:
        from cp_runtime.capability_store import CapabilityStore, CapabilityError
        from cp_runtime.capability_gate import GatePolicy
        from cp_runtime.common import RuntimeContractError
        try:
            profile_value, profile_error = _diagnostic_object(Path(profile_path))
            if profile_error or not profile_value:
                raise InstallError("PROJECT_PROFILE_UNREADABLE")
            store = CapabilityStore(Path(profile_path), Path(repo_path or "."))
            policy = GatePolicy(store).read()
            ready = bool(data.get("enhancement_selected")) and not data["component_errors"]["enhancement"]
            ready = ready and (data.get("mode") != "plugin" or (data.get("host_compatibility") or {}).get("compatible") is True)
            controls["controlled-write"] = {
                "availability": "NOT_ENABLED" if not policy or not policy["enabled"] else "UNKNOWN" if ready else "BLOCKED",
                "reason": "CONTROL_NOT_ENABLED" if not policy or not policy["enabled"] else
                          "OPERATION_AUTHORIZATION_NOT_EVALUATED" if ready else "CONTROL_RUNTIME_UNAVAILABLE",
            }
        except (OSError, ValueError, InstallError, RuntimeContractError):
            controls["controlled-write"] = {"availability": "BLOCKED", "reason": "CONTROL_PROFILE_UNVERIFIED"}
    if os.environ.get("CP_DELEGATION_BUDGET_REQUIRED", "").lower() in {"1", "true"}:
        from cp_runtime.delegation_budget import read_budget
        try:
            ledger = os.environ.get("CP_DELEGATION_BUDGET_PATH")
            if not ledger:
                raise ValueError("missing ledger")
            from cp_runtime.capability_store import safe_path
            budget = read_budget(safe_path(Path(ledger)))
            if profile_path and budget["identity"].get("project_id") != profile_value.get("project_id"):
                raise ValueError("project mismatch")
            controls["delegation-budget"] = {"availability": "UNKNOWN", "reason": "HOST_DISPATCH_PERMIT_NOT_EVALUATED"}
        except Exception:
            controls["delegation-budget"] = {"availability": "BLOCKED", "reason": "REQUIRED_BUDGET_UNAVAILABLE"}
    data["control_checks"] = controls
    return data


def _quick_installation_facts_once(scope: str, mode: Optional[str], repo_path: Optional[str]) -> Dict[str, Any]:
    """中文：在不校验宿主或 payload 的条件下读取有界持久安装事实。

    English: Read bounded persisted installation facts without host or payload validation.

    中文：快速状态刻意只是观察层；它不能把持久状态提升为当前注册、已加载运行时或完整性结论，也不会修复 journal 或写入缓存。
    English: Quick status is deliberately an observation tier. It must never promote persisted state into a current registration, loaded-runtime, or integrity claim, and it never repairs a journal or writes a cache.
    """
    repo = None
    non_git = False
    if scope == "repo":
        try:
            repo = git_root(Path(repo_path or "."))
        except InstallError:
            non_git = True
    source_state_path = state_path(scope, repo) if not non_git else None
    state, state_read_error = _diagnostic_object(source_state_path) if source_state_path else ({}, None)
    state_error = state_read_error
    if state and (type(state.get("schema_version")) is not int or
                  state.get("schema_version") not in {1, 2, 3} or state.get("package") != PACKAGE):
        state_error = "INSTALLATION_STATE_IDENTITY_INVALID"
    for key in ("components", "managed_hashes", "payload_identity"):
        if key in state and not isinstance(state[key], dict):
            state_error = "INSTALLATION_STATE_FIELDS_INVALID"
    base_state, base_read_error = _diagnostic_object(base_state_path()) if scope == "user" else ({}, None)
    base_state_error = base_read_error
    if base_state and (
            base_state.get("schema_version") != 1 or base_state.get("package") != PACKAGE
            or base_state.get("marketplace") != BASE_MARKETPLACE
            or Path(str(base_state.get("market_root", ""))) != base_marketplace_root()
            or base_state.get("status", "INSTALLED") not in {"INSTALLING", "INSTALLED", "RECOVERY_REQUIRED"}):
        base_state_error = "BASE_STATE_IDENTITY_INVALID"
    mode_error = _mode_error(state.get("mode"))
    selected_mode = mode if mode in {"plugin", "standalone"} else _normalized_mode(state.get("mode"))
    if state.get("mode") in {"plugin", "standalone"} and mode and mode != state["mode"]:
        mode_error = "REQUESTED_MODE_MISMATCH"
    live, transaction_error = (None, None)
    if not non_git:
        live, transaction_error = _diagnostic_journal(scope, repo)

    components = state.get("components") if isinstance(state.get("components"), dict) else {}
    enhancement = components.get("enhancement") if isinstance(components.get("enhancement"), dict) else {}
    declared = enhancement.get("status") if enhancement else None
    if state_error or mode_error:
        file_status = "UNVERIFIED"
    elif not state:
        file_status = "MISSING"
    elif declared in {"MANAGED", "INSTALLED", "PLUGIN_MANAGED"}:
        file_status = "DECLARED_MANAGED"
    else:
        file_status = "DECLARED_UNVERIFIED"
    if base_state_error:
        base_file_status = "UNVERIFIED"
    elif base_state:
        base_file_status = "DECLARED_MANAGED" if base_state.get("status", "INSTALLED") == "INSTALLED" else "DECLARED_UNVERIFIED"
    else:
        base_file_status = "MISSING"

    causes: List[Dict[str, str]] = []
    action: Optional[Dict[str, Any]] = None
    overall = "UNKNOWN"
    if live:
        # 中文：活动事务优先于格式错误的状态；恢复是唯一能安全建立新快照的可操作路径。
        # English: A live transaction takes precedence over a malformed state; recovery is the only actionable path that can safely establish a new snapshot.
        overall = "BLOCKED"
        causes.append({"id": "installation-transaction", "detail": "TRANSACTION_INCOMPLETE"})
        args = [sys.executable, str(ROOT / "scripts" / "package_manager.py"), "recover", "--scope", scope]
        if scope == "repo" and repo:
            args.extend(["--repo-path", str(repo)])
        action = _action_detail("RECOVER_INSTALLATION_TRANSACTION", "WRITE", args,
                                "存在未收敛安装事务。", "显式恢复既有事务后重新完整校验。", scope)
    elif transaction_error or state_error or base_state_error or mode_error:
        overall = "BLOCKED"
        reason = transaction_error or state_error or base_state_error or mode_error or "INSTALLATION_STATE_UNVERIFIED"
        causes.append({"id": "installation-state", "detail": str(reason)})
        action = _action_detail("INSPECT_MANAGED_STATE", "MANUAL", [],
                                "受管状态无法可靠读取。", "核对受管状态与已知备份，保留未知文件。", scope)
    elif non_git:
        causes.append({"id": "repository", "detail": "NON_GIT_DIRECTORY"})
    elif not state and not base_state:
        causes.append({"id": "installation-state", "detail": "INSTALLATION_STATE_MISSING"})
        action = _verify_action(scope, selected_mode, str(repo) if repo else None)

    return {
        "schema": "cp-assistant-quick-status/1", "query_tier": "QUICK", "collected_at": time.time(),
        "current_check": "NOT_EVALUATED",
        "package": PACKAGE, "version": VERSION, "scope": scope, "mode": selected_mode,
        "repo_path": str(repo) if repo else str(Path(repo_path or ".").absolute()) if scope == "repo" else None,
        "git_repository": not non_git if scope == "repo" else None,
        "overall": overall, "state_error": state_error, "base_state_error": base_state_error, "mode_error": mode_error,
        "transaction_error": transaction_error, "live_transaction": live,
        "installation_state": {"status": "UNREADABLE" if state_error or base_state_error else
                                 "ENHANCED_PRESENT" if state else "BASE_ONLY" if base_state else "MISSING",
                               "declared_version": state.get("version"), "declared_mode": state.get("mode")},
        "base_installation_state": {"status": "UNREADABLE" if base_state_error else "PRESENT" if base_state else "MISSING",
                                    "declared_version": base_state.get("version"), "declared_status": base_state.get("status")},
        "enhancement_installation_state": {"status": "UNREADABLE" if state_error else "PRESENT" if state else "MISSING",
                                           "declared_version": state.get("version"), "declared_mode": state.get("mode")},
        "file_state": {"status": file_status, "enhancement_declared_status": declared,
                       "base_status": base_file_status},
        "registration_state": {"status": "NOT_EVALUATED", "reason": "QUICK_HOST_PROBE_SKIPPED"},
        "loaded_state": {"status": "NOT_EVALUATED", "reason": "QUICK_CURRENT_TASK_LOAD_NOT_CHECKED"},
        "control_state": {"status": "NOT_EVALUATED", "reason": "QUICK_CONTROL_PREREQUISITES_NOT_CHECKED"},
        "last_full_validation_at": None,
        "not_evaluated": ["HOST_PROBE", "SOURCE_PAYLOAD_VERIFICATION", "MARKETPLACE_PAYLOAD_VERIFICATION",
                          "CACHE_PAYLOAD_VERIFICATION", "STABILITY_REREAD", "CONTROL_PREREQUISITES"],
        "causes": causes, "cause": causes, "next_action_detail": action,
        "read_only": True, "authorization_evidence": False,
        "_quick_stability": {"state": state, "state_error": state_error,
                              "base_state": base_state, "base_state_error": base_state_error,
                              "transaction": live, "transaction_error": transaction_error},
    }


def _quick_installation_facts(scope: str, mode: Optional[str], repo_path: Optional[str]) -> Dict[str, Any]:
    """中文：返回一对稳定的有界持久状态观察。

    English: Return a stable pair of bounded persisted-state observations.

    中文：该复读刻意排除宿主、payload 和控制探测；状态变化不能安全继承第一次快照的恢复动作，因此返回 UNKNOWN 并给出只读完整校验。
    English: This re-read intentionally excludes host, payload and control probing. A changed state cannot safely inherit a recovery action chosen from the first snapshot, so it is returned as UNKNOWN with a read-only full verification.
    """
    first = _quick_installation_facts_once(scope, mode, repo_path)
    second = _quick_installation_facts_once(scope, mode, repo_path)
    stable = first.pop("_quick_stability") == second.pop("_quick_stability")
    if not stable:
        first["overall"] = "UNKNOWN"
        first["sample_error"] = "INSTALLATION_CHANGED_DURING_READ"
        first["causes"] = [*first["causes"], {"id": "installation-state", "detail": first["sample_error"]}]
        first["cause"] = first["causes"]
        first["next_action_detail"] = _verify_action(scope, first["mode"], first.get("repo_path"))
    return first


def status(scope: str, mode: Optional[str], repo_path: Optional[str], summary: bool = False,
           profile_path: Optional[str] = None, quick: bool = False) -> None:
    if quick:
        # 中文：--profile 在 QUICK 中刻意无效：不评估控制检查，快速输出不能授权操作。
        # English: --profile intentionally has no effect in QUICK: control checks are not evaluated and quick output cannot authorize an operation.
        print(json.dumps(_quick_installation_facts(scope, mode, repo_path), ensure_ascii=False, indent=2))
        return
    data = _diagnostic_facts(scope, mode, repo_path, profile_path)
    data["ux"] = _ux_summary(data)
    print(json.dumps(status_summary(data) if summary else data, ensure_ascii=False, indent=2))


def _inventory_candidates(scope: str, mode: str, repo: Optional[Path]) -> List[Path]:
    if scope == "repo":
        assert repo is not None
        return [repo / ".agents" / "skills" / name for name in skill_names() + deprecated_skill_names()]
    ch = codex_home()
    paths = [ch / "AGENTS.md", ch / "tools" / "cp-runtime.py", ch / "tools" / "evolution.py"]
    paths.extend(ch / "agents" / item.name for item in agent_files())
    if mode == "plugin":
        paths.extend([plugin_marketplace_payload(), plugin_marketplace_manifest(), plugin_cache_root()])
    else:
        paths.extend(user_skills_home() / name for name in skill_names() + deprecated_skill_names())
        paths.extend([ch / "runtime" / "cp_runtime", ch / "cp-assistant-hooks" / "cp_hook.py",
                      ch / "cp-assistant-hooks" / "cp_gate.py", ch / "hooks.json"])
    return paths


def _inventory_digest(path: Path, managed_global: bool = False) -> str:
    """中文：有界检查已知受管目标，沿用既有目录摘要算法。

    English: Bound managed-target reads while preserving the existing tree digest algorithm.
    """
    from cp_runtime.capability_store import bounded_read, safe_path
    target = safe_path(path)
    maximum = 64 * 1024 * 1024
    if target.is_file():
        raw = bounded_read(target, maximum)
        return managed_global_sha256(target) if managed_global else hashlib.sha256(raw).hexdigest()
    pending, files = [target], []
    visited = 0
    while pending:
        visited += 1
        if visited > 2000:
            raise InstallError("INVENTORY_DIRECTORY_LIMIT")
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                item = safe_path(Path(entry.path))
                if entry.is_dir(follow_symlinks=False):
                    pending.append(item)
                    if len(pending) + visited > 2000:
                        raise InstallError("INVENTORY_DIRECTORY_LIMIT")
                elif entry.is_file(follow_symlinks=False):
                    files.append(item)
                    if len(files) > 2000:
                        raise InstallError("INVENTORY_FILE_LIMIT")
                else:
                    raise InstallError("INVENTORY_NON_REGULAR_ENTRY")
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda item: item.as_posix()):
        raw = bounded_read(item, maximum)
        maximum -= len(raw)
        digest.update(item.relative_to(target).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def inventory(scope: str, mode: str, repo_path: Optional[str]) -> Dict[str, Any]:
    """中文：只读列出已知受管目标、漂移和未知候选。 English: Read-only managed, drifted, and unknown candidate inventory."""
    repo: Optional[Path] = None
    base_path = Path(repo_path or ".").expanduser().absolute() if scope == "repo" else None
    if scope == "repo":
        try:
            repo = git_root(base_path)
        except InstallError:
            return {"package":PACKAGE, "version":VERSION, "scope":scope, "mode":mode,
                    "overall":"BASIC_ONLY", "git_repository":False, "base_path":str(base_path),
                    "state_present":False, "items":[], "unknown_assets_preserved":True,
                    "delete_authorized":False,
                    "remediation":["基础文件与说明能力可用；仓库身份、安装和 Git 证据不适用。"]}
    sp = state_path(scope, repo)
    state, state_error = _diagnostic_object(sp)
    if state_error or ("managed_hashes" in state and not isinstance(state["managed_hashes"], dict)):
        return {"package": PACKAGE, "version": VERSION, "scope": scope, "mode": mode,
                "overall": "ERROR", "state_present": bool(state), "state_path": str(sp),
                "items": [], "unknown_assets_preserved": True, "delete_authorized": False,
                "reason": state_error or "STATE_HASHES_INVALID",
                "remediation": ["Inspect the managed state and known backups; no assets were changed."]}
    hashes = state.get("managed_hashes") if isinstance(state.get("managed_hashes"), dict) else {}
    rows = []
    if state:
        for raw, expected in sorted(hashes.items()):
            path = Path(raw)
            try:
                if scope == "repo":
                    ensure_inside(path, repo)
                    reject_link_ancestors(path, repo)
                else:
                    allowed_roots = (codex_home(), user_skills_home(), plugin_marketplace_root())
                    if not any(path_inside(path, root) for root in allowed_roots):
                        raise InstallError("target outside managed roots")
                    reject_link_ancestors(path)
            except InstallError:
                rows.append({"path":str(path), "status":"UNSAFE_PATH", "expected_sha256":str(expected),
                             "actual_sha256":None})
                continue
            is_global_agents = (
                scope == "user"
                and _containment_path(path) == _containment_path(codex_home() / "AGENTS.md")
            )
            try:
                _io_path(path).stat()
                actual = _inventory_digest(path, is_global_agents)
                status_name = "MANAGED" if str(expected) == actual else "DRIFT"
            except FileNotFoundError:
                actual, status_name = "missing", "MISSING"
            except Exception:
                actual, status_name = None, "UNREADABLE"
            rows.append({"path":str(path), "status":status_name, "expected_sha256":str(expected),
                         "actual_sha256":actual})
    else:
        for path in _inventory_candidates(scope, mode, repo):
            try:
                _io_path(path).lstat()
                reject_link_ancestors(path)
                rows.append({"path":str(path), "status":"UNKNOWN_OWNER", "actual_sha256":_inventory_digest(path)})
            except FileNotFoundError:
                continue
            except InstallError:
                rows.append({"path":str(path), "status":"UNSAFE_PATH", "actual_sha256":None})
            except Exception:
                rows.append({"path":str(path), "status":"UNREADABLE", "actual_sha256":None})
    overall = ("ERROR" if any(row["status"] == "UNSAFE_PATH" for row in rows) else
               ("PASS" if state and all(row["status"] == "MANAGED" for row in rows) else
                ("DEGRADED" if state else "UNKNOWN")))
    return {"package":PACKAGE, "version":VERSION, "scope":scope, "mode":mode, "overall":overall,
            "git_repository":True if scope == "repo" else None, "base_path":str(base_path) if base_path else None,
            "state_present":bool(state), "state_path":str(sp), "items":rows,
            "unknown_assets_preserved":True, "delete_authorized":False,
            "remediation":(["先恢复或重新安装受管 state；未知资产不会自动删除。"] if not state else
                           (["先处理缺失或漂移目标，再执行变更操作。"] if overall == "DEGRADED" else []))}


def doctor(recover: bool = False, scope: str = "user", repo_path: Optional[str] = None,
           summary: bool = False, profile_path: Optional[str] = None) -> bool:
    if recover:
        recover_transaction(scope, repo_path)
        return True
    data = _diagnostic_facts(scope, None, repo_path, profile_path)
    checks: List[Dict[str, Any]] = []
    remediation: List[str] = []

    def check(identifier: str, result: str, detail: str, fix: str = "") -> None:
        checks.append({"id": identifier, "status": result, "detail": detail, "remediation": fix or None})
        if result in {"WARN", "ERROR"} and fix:
            remediation.append(fix)

    check("python", "PASS", ".".join(map(str, sys.version_info[:3])))
    check("git", "NOT_APPLICABLE" if data.get("git_repository") is False else
          ("PASS" if shutil.which("git") else "WARN"),
          str(shutil.which("git") or "not found"))
    try:
        report = payload_report(ROOT)
        check("payload", "PASS", "source payload files=%s" % report.get("file_count"))
    except (OSError, ValueError, InstallError) as exc:
        check("payload", "ERROR", "SOURCE_PAYLOAD_UNVERIFIED:" + type(exc).__name__,
              "重新下载并校验当前发行包。")
    check("state", "ERROR" if data.get("state_error") or data.get("base_state_error") or data.get("mode_error")
          else "NOT_APPLICABLE" if data.get("git_repository") is False
          else "PASS" if data.get("state") or data.get("base_state") else "WARN",
          str(data.get("state_error") or data.get("base_state_error") or data.get("mode_error") or
              ("present" if data.get("state") or data.get("base_state") else "missing")))
    check("transaction", "ERROR" if data.get("live_transaction") or data.get("transaction_error") else "PASS",
          str(data.get("transaction_error") or ("active" if data.get("live_transaction") else "none")))
    check("base-skills", "PASS" if len(skill_names()) == 10 else "ERROR", "source count=%d" % len(skill_names()))
    try:
        hook_count = len(json.loads((ROOT / "hooks" / "enhancement-hooks.json").read_text(encoding="utf-8"))["hooks"])
        check("hooks", "PASS" if hook_count == 8 else "ERROR", "source hook types=%d" % hook_count)
    except (OSError, ValueError, KeyError, TypeError):
        check("hooks", "ERROR", "SOURCE_HOOKS_UNVERIFIED")
    check("child-agent-policy", "PASS" if len(agent_files()) == 7 else "WARN",
          "source reviewers=%d; optional for serial work" % len(agent_files()))
    check("controlled-write", "NOT_APPLICABLE", "OPERATION_AUTHORIZATION_NOT_EVALUATED")
    check("observation", "NOT_APPLICABLE", "RUNTIME_OBSERVATION_NOT_EVALUATED")
    projected = _ux_summary(data)
    base_result = next((item for item in projected["capabilities"] if item["id"] == "base-plugin"), {})
    plugin_status = "NOT_APPLICABLE" if scope == "repo" else (
        "ERROR" if data.get("mode_error") or data.get("state_error") or
        base_result.get("availability") == "UNAVAILABLE" else
        "WARN" if base_result.get("availability") == "UNKNOWN" else "PASS"
    )
    check("plugin", plugin_status, "; ".join(base_result.get("reason_codes") or ["OUTSIDE_SCOPE"]))
    ux = _merge_doctor_checks_into_ux(projected, checks)
    source_failure = next((item for item in checks if item["status"] == "ERROR"
                           and item["id"] in {"payload", "hooks", "base-skills"}), None)
    if source_failure:
        ux["next_action_detail"] = _action_detail(
            "VERIFY_SOURCE_PACKAGE", "MANUAL", [], "当前诊断源包校验失败。", "重新下载并校验当前发行包。", scope,
        )
    elif ux.get("next_action_detail") and ux["next_action_detail"].get("code") == "VERIFY_INSTALLATION":
        ux["next_action_detail"] = _verify_action(scope, data["mode"], data.get("repo_path"))
    capability = data.get("capability_profile") or {}
    base = next((item for item in ux["capabilities"] if item["id"] == "base-plugin"), {})
    data.update({
        "target_codex": TARGET_CODEX_VERSION, "supported_codex_versions": list(SUPPORTED_CODEX_VERSIONS),
        "python": sys.executable, "python_version": ".".join(map(str, sys.version_info[:3])),
        "home": str(Path.home()), "codex_home": str(codex_home()), "user_skills_home": str(user_skills_home()),
        "plugin_marketplace_root": str(plugin_marketplace_root()), "skill_count": len(skill_names()),
        "reviewer_count": len(agent_files()), "plugin_manifest": str(ROOT / ".codex-plugin" / "plugin.json"),
        "hooks_manifest": str(ROOT / "hooks" / "hooks.json"), "payload_manifest": str(ROOT / PAYLOAD_MANIFEST_NAME),
        "plugin_cache_root": str(plugin_cache_root()), "git": shutil.which("git"),
        "codex": _codex_executable() if _codex_available() else None,
        "codex_version": capability.get("codex_version_output"),
        "transaction": None if data.get("git_repository") is False else
                       str(transaction_path(scope, Path(data["repo_path"]) if scope == "repo" else None)),
        "overall": ux["overall"], "checks": checks, "remediation": remediation, "ux": ux,
        "base_capabilities_available": base.get("availability") == "AVAILABLE" or scope == "repo",
    })
    print(json.dumps(doctor_summary(data) if summary else data, ensure_ascii=False, indent=2))
    return ux["overall"] == "PASS"


def main() -> None:
    p=argparse.ArgumentParser(description="Codex 跨项目长期技术助手 V%s 安装器" % VERSION)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("install","verify","uninstall"):
        q=sub.add_parser(name)
        q.add_argument("--scope",choices=["user","repo"],default="user")
        q.add_argument("--mode",choices=["plugin","standalone"],default="plugin")
        q.add_argument("--repo-path")
        if name in {"install","uninstall"}: q.add_argument("--dry-run",action="store_true")
        if name in {"install","uninstall"}: q.add_argument("--force",action="store_true")
    doctor_parser=sub.add_parser("doctor")
    doctor_parser.add_argument("--recover", action="store_true")
    doctor_parser.add_argument("--scope", choices=["user", "repo"], default="user")
    doctor_parser.add_argument("--repo-path")
    doctor_parser.add_argument("--profile", help="Explicit project profile for control-prerequisite diagnostics; never changes policy")
    doctor_parser.add_argument("--strict", action="store_true")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument("--summary", action="store_true")
    status_parser=sub.add_parser("status")
    status_parser.add_argument("--scope",choices=["user","repo"],default="user")
    status_parser.add_argument("--mode",choices=["plugin","standalone"],default=None)
    status_parser.add_argument("--repo-path")
    status_parser.add_argument("--profile", help="Explicit project profile for control-prerequisite diagnostics; never changes policy")
    status_parser.add_argument("--json",action="store_true")
    status_parser.add_argument("--quick", action="store_true",
                               help="Read bounded persisted facts only; skips host probing, payload verification, and stability rereads")
    recover_parser=sub.add_parser("recover")
    recover_parser.add_argument("--scope",choices=["user","repo"],default="user")
    recover_parser.add_argument("--repo-path")
    inventory_parser=sub.add_parser("inventory")
    inventory_parser.add_argument("--scope",choices=["user","repo"],default="user")
    inventory_parser.add_argument("--mode",choices=["plugin","standalone"],default="plugin")
    inventory_parser.add_argument("--repo-path")
    inventory_parser.add_argument("--json",action="store_true")
    args=p.parse_args()
    if args.command=="doctor":
        if args.recover:
            repo = git_root(Path(args.repo_path or ".")) if args.scope == "repo" else None
            with scope_lock(args.scope, repo): doctor(True, args.scope, str(repo) if repo else None)
            return
        # 中文：常规调用者默认获得可行动摘要；脚本调用方通过 --json 保留完整稳定字段。
        # English: Ordinary users receive an actionable summary by default; --json retains stable full fields for scripts.
        ok = doctor(False, args.scope, args.repo_path, summary=not args.json, profile_path=args.profile)
        if args.strict and not ok: raise SystemExit(2)
        return
    if args.command=="status": status(args.scope,args.mode,args.repo_path,summary=not args.json,profile_path=args.profile,quick=args.quick); return
    if args.command=="inventory":
        print(json.dumps(inventory(args.scope,args.mode,args.repo_path),ensure_ascii=False,indent=2)); return
    if args.command=="recover":
        repo = git_root(Path(args.repo_path or ".")) if args.scope == "repo" else None
        with scope_lock(args.scope, repo): recover_transaction(args.scope, str(repo) if repo else None)
        return
    repo = git_root(Path(args.repo_path or ".")) if args.scope == "repo" else None
    if args.command == "install" and args.scope == "user":
        # 中文：危险目标必须在锁文件或事务文件出现之前失败关闭。
        # English: Dangerous targets must fail closed before any lock or journal is created.
        validate_user_install_target()
    with scope_lock(args.scope, repo):
        if args.command=="install":
            if args.scope=="repo": install_repo(str(repo),args.dry_run)
            else: install_user(args.mode,args.dry_run,args.force)
        elif args.command=="verify": verify(args.scope,args.mode,str(repo) if repo else None)
        elif args.command=="uninstall": uninstall(args.scope,args.mode,str(repo) if repo else None,args.force,args.dry_run)

if __name__=="__main__":
    try: main()
    except InstallError as exc:
        print("[ERROR]",exc,file=sys.stderr); raise SystemExit(2)
