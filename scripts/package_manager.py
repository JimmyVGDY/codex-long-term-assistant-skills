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
VERSION = "7.4.4"
MARKETPLACE = "cp-assistant-local"
COMPATIBILITY_REGISTRY_PATH = ROOT / "config" / "codex-compatibility-v1.json"
COMPATIBILITY_REGISTRY = load_registry(COMPATIBILITY_REGISTRY_PATH, VERSION)
TARGET_CODEX_VERSION = str(COMPATIBILITY_REGISTRY["window_policy"]["anchor"])
# 中文：当前包按冻结的稳定发行序列支持当前版和前十个稳定发行版。
# English: The current package supports the frozen current stable release and ten preceding stable releases.
SUPPORTED_CODEX_VERSIONS = tuple(item["version"] for item in COMPATIBILITY_REGISTRY["versions"])
REPAIRABLE_MARKETPLACE_STATE_VERSIONS = frozenset({
    "6.1.0", "6.2.0", "6.3.0", "7.2.0", "7.3.0", "7.4.0",
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


def ensure_inside(path: Path, root: Path) -> None:
    p = path.absolute()
    r = root.absolute()
    try:
        p.relative_to(r)
    except ValueError as exc:
        raise InstallError("目标路径越过受管根目录: %s" % path) from exc


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


def hook_fragment(script_path: Path) -> Dict[str, Any]:
    command = '"%s" "%s"' % (sys.executable.replace('"', '\\"'), str(script_path).replace('"', '\\"'))
    return {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "PreToolUse": [{"matcher": "Agent|spawn_agent", "hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "SubagentStart": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "SubagentStop": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "Stop": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}],
    }


def merge_hooks(path: Path, script_path: Path) -> None:
    data = load_json(path, {}) or {}
    if not isinstance(data, dict):
        raise InstallError("现有 hooks.json 不是 JSON 对象")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError("现有 hooks.json 的 hooks 不是对象")
    fragment = hook_fragment(script_path)
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
        if "cp-assistant-hooks/cp_hook.py" in command:
            return True
    return False


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
    except PayloadIntegrityError as exc:
        raise InstallError("Plugin payload 校验失败 (%s): %s" % (root, exc)) from exc


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


def _probe_plugin_host() -> Dict[str, Any]:
    """中文：读取已验证 Codex CLI 版本的 Plugin 宿主能力，不修改状态。

    English: Read the Plugin host capability profile for verified Codex CLI versions without
    changing state.
    """
    version_text = _codex_version_text()
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
    result = _run_codex(["plugin", "list", "--json"], check=False)
    try:
        data = json.loads(result.stdout or "")
    except json.JSONDecodeError:
        data = None
    normalized_target = None
    list_error = ""
    list_ok = False
    if result.returncode == 0 and version_profile is not None:
        try:
            json_profile = COMPATIBILITY_REGISTRY["profiles"]["plugin_json"][version_profile["plugin_json_profile"]]
            normalized_target = normalize_plugin_list(data, PACKAGE, MARKETPLACE, None, json_profile)
            list_ok = True
        except CompatibilityError as exc:
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
        probe = _run_codex(args, check=False)
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
        "plugin_json_profile", "hook_profile", "commands", "plugin_list_contract",
        "capability_digest",
    )
    return {key: profile.get(key) for key in keys}


_HOST_BINDING_KEYS = {
    "codex_version", "executable_path", "executable_sha256", "registry_schema",
    "registry_digest", "marketplace_profile", "plugin_cli_profile",
    "plugin_json_profile", "hook_profile", "commands", "plugin_list_contract",
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
    for key in ("marketplace_profile", "plugin_cli_profile", "plugin_json_profile", "hook_profile"):
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


def _host_compatibility_status(state: Mapping[str, Any]) -> Dict[str, Any]:
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
        current = _probe_plugin_host()
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
        targets.extend([("runtime", ch / "runtime" / "cp_runtime"), ("hook-script", ch / "cp-assistant-hooks" / "cp_hook.py"), ("hooks-json", ch / "hooks.json")])
    else:
        targets.extend([
            ("plugin-payload", plugin_marketplace_payload()),
            ("marketplace-manifest", plugin_marketplace_manifest()),
            ("plugin-cache", plugin_cache_root()),
        ])
    for _label, target in targets:
        reject_link_ancestors(target.parent)
    old_state = load_json(state_path("user"), {}) or {}
    migrated_old_state = migrate_state_to_v3(old_state, "user", mode)
    if dry_run:
        print(json.dumps({"scope":"user","mode":mode,"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_schema":old_state.get("schema_version"),
                          "state_migration":"legacy-to-v3" if old_state.get("schema_version") in {1, 2} else "none",
                          "backup_required":True,"targets":[str(x[1]) for x in targets],
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
            dst = ch / "runtime" / "cp_runtime"; copy_atomic(ROOT / "runtime" / "cp_runtime", dst); _record_applied(journal, "runtime", dst)
            dst = ch / "cp-assistant-hooks" / "cp_hook.py"; copy_atomic(ROOT / "hooks" / "cp_hook.py", dst); _record_applied(journal, "hook-script", dst)
            merge_hooks(ch / "hooks.json", ch / "cp-assistant-hooks" / "cp_hook.py")
            _record_applied(journal, "hooks-json", ch / "hooks.json")
        else:
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
        else:
            cache_report = None
        managed = {str(path): tree_sha256(path) for _label, path in targets if _io_path(path).exists() and _label not in {"global", "hooks-json", "install-state"}}
        managed[str(gp)] = hashlib.sha256((ROOT / "global" / "AGENTS.md").read_bytes()).hexdigest()
        state = dict(migrated_old_state)
        state.update({"schema_version":3,"package":PACKAGE,"version":VERSION,"scope":"user","mode":mode,
                      "installed_at":time.time(),"backup":str(backup),"managed_hashes":managed,
                      "previous_backup":old_state.get("backup"),
                      "capability_profile":_host_binding(capability_profile) if mode == "plugin" else {}})
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
    if dry_run:
        print(json.dumps({"scope":"repo","repo":str(repo),"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_migration":"legacy-to-v3" if old_state.get("schema_version") in {1, 2} else "none",
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
        else:
            market = plugin_marketplace_root()
            plugin=market/"plugins"/PACKAGE
            for name in deprecated_skill_names():
                if _io_path(plugin/"skills"/name).exists(): errors.append("Plugin 遗留旧 Skill %s" % name)
            if not _io_path(market/".agents"/"plugins"/"marketplace.json").is_file(): errors.append("缺少 Codex Marketplace manifest")
            if not _io_path(plugin/".codex-plugin"/"plugin.json").is_file(): errors.append("缺少 Plugin")
            if not _io_path(plugin/"hooks"/"hooks.json").is_file(): errors.append("缺少 Plugin Hooks")
            if not _io_path(plugin/"hooks"/"seal_worker.py").is_file(): errors.append("缺少延迟封印 Worker")
            if os.name == "nt" and not _io_path(plugin/"hooks"/"cp_hook.cmd").is_file(): errors.append("缺少 Windows Hook 启动器")
            if _io_path(plugin/"hooks"/"hooks.json").is_file():
                hook_manifest = load_json(plugin/"hooks"/"hooks.json", {}) or {}
                hook_groups = hook_manifest.get("hooks") or {}
                for hook_name in ("UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop", "Stop", "SessionEnd"):
                    entries = hook_groups.get(hook_name) or []
                    commands = [
                        hook.get("commandWindows", "")
                        for entry in entries
                        for hook in (entry.get("hooks") or [])
                        if isinstance(hook, dict)
                    ]
                    if os.name == "nt" and not any("cp_hook.cmd" in command for command in commands):
                        errors.append("Windows Hook 启动命令缺失 %s" % hook_name)
                    quoted_prefix = 'cmd.exe /d /c ""%PLUGIN_ROOT%\\hooks\\cp_hook.cmd" '
                    if os.name == "nt" and not any(command.startswith(quoted_prefix) and command.endswith('"')
                                                     for command in commands):
                        errors.append("Windows Hook 启动路径未完整引用 %s" % hook_name)
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


def status(scope: str, mode: str, repo_path: Optional[str]) -> None:
    repo = git_root(Path(repo_path or ".")) if scope == "repo" else None
    state = load_json(state_path(scope, repo), {}) or {}
    live = _load_live_journal(scope, repo)
    active, detail = _plugin_activation_status() if scope == "user" and _codex_available() else (False, "not checked")
    host_compatibility = None
    if scope == "user" and mode == "plugin":
        host_compatibility = _host_compatibility_status(state)
    ch = codex_home()
    payload = None
    if scope == "user" and mode == "plugin" and plugin_cache_root().is_dir():
        try:
            payload = {"source": payload_report(ROOT), "marketplace": payload_report(plugin_marketplace_payload()),
                       "cache": payload_report(plugin_cache_root())}
        except InstallError as exc:
            payload = {"ok": False, "error": str(exc)}
    data = {"package": PACKAGE, "version": VERSION, "scope": scope, "state": state,
            "live_transaction": live, "plugin_activation": {"active": active, "detail": detail},
            "host_compatibility": host_compatibility,
            "payload_identity": payload,
            "skills": skill_names(), "reviewers": [p.name for p in agent_files()],
            "hooks": str(ch / "hooks.json") if scope == "user" else None}
    print(json.dumps(data, ensure_ascii=False, indent=2))


def doctor(recover: bool = False, scope: str = "user", repo_path: Optional[str] = None) -> None:
    if recover:
        recover_transaction(scope, repo_path)
        return
    codex_exe = _codex_executable() if _codex_available() else None
    codex_version = None
    if codex_exe:
        try:
            codex_version = _codex_version_text()
        except Exception:
            codex_version = None
    capability = None
    if codex_exe:
        try:
            capability = _probe_plugin_host()
        except Exception as exc:
            capability = {"ok": False, "error": str(exc)}
    state = load_json(state_path(scope, git_root(Path(repo_path or ".")) if scope == "repo" else None), {}) or {}
    host_compatibility = (
        _host_compatibility_status(state)
        if scope == "user" and state.get("mode") == "plugin"
        else None
    )
    print(json.dumps({
        "package":PACKAGE,"version":VERSION,"target_codex":TARGET_CODEX_VERSION,
        "supported_codex_versions":list(SUPPORTED_CODEX_VERSIONS),"python":sys.executable,
        "home":str(Path.home()),"codex_home":str(codex_home()),
        "user_skills_home":str(user_skills_home()),
        "plugin_marketplace_root":str(plugin_marketplace_root()),
        "skill_count":len(skill_names()),"reviewer_count":len(agent_files()),
        "plugin_manifest":str(ROOT/".codex-plugin"/"plugin.json"),
        "hooks_manifest":str(ROOT/"hooks"/"hooks.json"), "transaction": str(transaction_path("user")),
        "payload_manifest":str(ROOT/PAYLOAD_MANIFEST_NAME),
        "plugin_cache_root":str(plugin_cache_root()),
        "git":shutil.which("git"),"codex":codex_exe,"codex_version":codex_version,
        "capability_profile":capability,"host_compatibility":host_compatibility
    },ensure_ascii=False,indent=2))


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
    status_parser=sub.add_parser("status")
    status_parser.add_argument("--scope",choices=["user","repo"],default="user")
    status_parser.add_argument("--mode",choices=["plugin","standalone"],default="plugin")
    status_parser.add_argument("--repo-path")
    status_parser.add_argument("--json",action="store_true")
    recover_parser=sub.add_parser("recover")
    recover_parser.add_argument("--scope",choices=["user","repo"],default="user")
    recover_parser.add_argument("--repo-path")
    args=p.parse_args()
    if args.command=="doctor":
        repo = git_root(Path(args.repo_path or ".")) if args.scope == "repo" else None
        with scope_lock(args.scope, repo): doctor(args.recover, args.scope, str(repo) if repo else None)
        return
    if args.command=="status": status(args.scope,args.mode,args.repo_path); return
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
