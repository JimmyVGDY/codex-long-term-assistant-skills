#!/usr/bin/env python3
"""V6 安装/验证/卸载器。

设计目标：官方账户 Skill 目录、Plugin-first、standalone 兼容、仓库作用域隔离、
路径逃逸防护、备份、漂移检测与 dry-run。不会自动删除未知使用方资产。
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

from payload_integrity import (MANIFEST_NAME as PAYLOAD_MANIFEST_NAME,
                               PayloadIntegrityError, load_manifest as load_payload_manifest,
                               verify_payload)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.integrity import init_keyring, verify_keyring  # noqa: E402
MANIFEST_PATH = ROOT / "manifest.json"
PACKAGE = "codex-cross-project-engineering-assistant"
VERSION = "6.6.0"
MARKETPLACE = "cp-assistant-local"
BEGIN = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:BEGIN -->"
END = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:END -->"

class InstallError(RuntimeError):
    pass


JOURNAL_SCHEMA = 1
JOURNAL_STAGES = {"PREPARED", "BACKED_UP", "APPLYING", "ACTIVATING", "COMMITTED",
                  "ROLLBACK_STARTED", "ROLLED_BACK", "RECOVERY_REQUIRED"}


def _hard_crash(point: str) -> None:
    """Test-only true process termination; never enabled without an explicit env point."""
    if os.environ.get("CP_ASSISTANT_TEST_HARD_CRASH_POINT") == point:
        os._exit(91)


def transaction_path(scope: str, repo: Optional[Path] = None) -> Path:
    """One durable journal per scope.  It is deliberately outside a backup."""
    return state_path(scope, repo).with_name("cp-assistant-v6-transaction.json")


@contextlib.contextmanager
def scope_lock(scope: str, repo: Optional[Path] = None) -> Iterable[None]:
    """Serialize every mutating operation in a user/repository scope."""
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
                # Closing the CRT descriptor releases its byte-range lock.  Calling
                # LK_UNLCK after Python's buffered file handling is unreliable on
                # Windows (the current byte can be changed by buffering).
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
        # A controlled exception leaves the durable journal for `doctor --recover`.
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
    """Archive a terminal transaction and remove its live recovery marker."""
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
    """Do not delete a target changed by somebody after this transaction."""
    label = str(record.get("label") or "")
    if label in {"global", "hooks-json"}:
        return True  # restoration is merge-based and preserves external edits.
    target = Path(str(record["target"]))
    if not _io_path(target).exists():
        return True
    current = tree_sha256(target)
    expected = (journal.get("applied_hashes") or {}).get(str(target))
    if expected and current == expected:
        return True
    # A persisted mutation intent may precede the atomic swap. The untouched
    # pre-transaction tree is also owned and safe to restore idempotently.
    return bool(record.get("existed") and record.get("sha256") and current == record.get("sha256"))


def _record_applied(journal: Dict[str, Any], label: str, target: Path) -> None:
    """Persist ownership immediately after one destructive target action."""
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
    """Persist the only complete post-mutation hash before an atomic target swap."""
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
    """Return an extended-length Windows path for filesystem I/O.

    Codex user homes, Marketplace roots and timestamped backup directories can
    collectively exceed the legacy 260-character limit even when every
    individual component is valid. Keep logical paths and persisted manifests
    human-readable, but use the Win32 extended-length prefix at I/O boundaries.
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
        # Some Codex Desktop/WSL bridge sessions can inherit `/mnt/c/...` even while the
        # installer itself is executing under native Windows Python. Convert it before any
        # ownership/reparse checks so we never create a literal `\\mnt\\c` tree on Windows.
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
    # Codex 当前账户级 Skills 规范目录，不随 CODEX_HOME 改写。
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
    """Reject any link/reparse descendant without following it."""
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
    # Keep the staging component deliberately short. Repeating a long Plugin
    # name plus a "payload" component can cross the legacy Windows MAX_PATH
    # boundary even when the final destination itself is valid.
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
    # 先移除本包旧命令，避免重复安装。
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
    """Identify only the standalone Hook command owned by this package."""
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
    """Restore only this package's AGENTS block and preserve user edits.

    The installer owns the marked block, not the whole AGENTS.md file. During
    uninstall an older managed block is restored when upgrading from an older
    release; user content added before or after installation remains intact.
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
    """Remove current package Hooks, restore prior package Hooks, keep others."""
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


def skill_names() -> List[str]:
    return [str(item["name"]) for item in manifest().get("skills", [])]


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
    """Preserve all prior/unknown fields while making the V6.6 identity fields explicit."""
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


def _merged_marketplace_manifest(existing: Any) -> Dict[str, Any]:
    data = dict(existing) if isinstance(existing, dict) else {}
    plugins = [dict(item) for item in data.get("plugins", []) if isinstance(item, dict)
               and item.get("name") != PACKAGE]
    plugins.append({"name": PACKAGE,
                    "source": {"source": "local", "path": "./plugins/%s" % PACKAGE},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity"})
    data["name"] = MARKETPLACE
    interface = data.get("interface")
    if not isinstance(interface, dict):
        interface = {}
    interface.setdefault("displayName", "Codex Cross Project Assistant Local")
    data["interface"] = interface
    # V6.1-V6.3 wrote a legacy `owner` block that Codex 0.150.1 no longer
    # accepts in a local marketplace manifest. This is a known managed field,
    # not an unknown external entry.
    data.pop("owner", None)
    data["plugins"] = plugins
    return data


def plugin_payload_source(tmp: Path) -> Path:
    name = PACKAGE
    out = tmp / name
    out.mkdir(parents=True)
    for rel in (".codex-plugin", "skills", "hooks", "runtime"):
        shutil.copytree(_io_path(ROOT / rel), _io_path(out / rel))
    shutil.copy2(_io_path(ROOT / PAYLOAD_MANIFEST_NAME), _io_path(out / PAYLOAD_MANIFEST_NAME))
    payload_report(out)
    return out


def _codex_executable() -> str:
    exe = shutil.which("codex")
    if not exe:
        raise InstallError("未找到 codex CLI；Plugin 模式需要 Codex 0.150.1 或兼容版本。可改用 --mode standalone")
    return exe


def _run_codex(args: List[str], timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [_codex_executable()] + args
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home())
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env, timeout=timeout)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InstallError("Codex CLI 执行失败: %s；%s" % (" ".join(cmd), detail[-2000:]))
    return result


def _activate_plugin(market: Path) -> None:
    # 0.150.1: marketplace add accepts the Marketplace ROOT, then plugin add installs/enables it.
    _run_codex(["plugin", "marketplace", "add", str(market)])
    _run_codex(["plugin", "add", "%s@%s" % (PACKAGE, MARKETPLACE)])


def _deactivate_plugin(check: bool = True) -> None:
    result = _run_codex(["plugin", "remove", "%s@%s" % (PACKAGE, MARKETPLACE)], check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        # Already-absent is acceptable during rollback/uninstall.
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
    """Remove only empty directories created for this marketplace; never recurse."""
    market = plugin_marketplace_root()
    for candidate in (market / "plugins", market / ".agents" / "plugins", market / ".agents", market):
        try:
            _io_path(candidate).rmdir()
        except (FileNotFoundError, OSError):
            pass


def _codex_version_text() -> str:
    result = _run_codex(["--version"], check=False)
    return (result.stdout or result.stderr or "").strip()


def _plugin_activation_status(expected_version: Optional[str] = None) -> Tuple[bool, str]:
    result = _run_codex(["plugin", "list", "--json"], check=False)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "codex plugin list failed").strip()
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False, "codex plugin list --json 返回了非 JSON 数据"
    for item in data.get("installed", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or str(item.get("pluginId") or "").split("@", 1)[0]
        marketplace = item.get("marketplaceName") or (str(item.get("pluginId") or "").split("@", 1)[1] if "@" in str(item.get("pluginId") or "") else "")
        if name == PACKAGE and marketplace == MARKETPLACE:
            version_matches = expected_version is None or str(item.get("version") or "") == expected_version
            ok = item.get("installed") is True and item.get("enabled") is True and version_matches
            return ok, json.dumps(item, ensure_ascii=False)
    return False, "未在 Codex installed 列表中发现 %s@%s" % (PACKAGE, MARKETPLACE)


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
    """Read-only capability profile for the supported 0.150.1 Plugin host."""
    version = _codex_version_text()
    version_ok = bool(re.search(r"(?:^|\s)0\.150\.1(?:\s|$)", version))
    result = _run_codex(["plugin", "list", "--json"], check=False)
    try:
        data = json.loads(result.stdout or "")
    except json.JSONDecodeError:
        data = None
    list_ok = result.returncode == 0 and isinstance(data, dict) and isinstance(data.get("installed", []), list)
    commands: Dict[str, bool] = {}
    for name, args in {
        "marketplace_add": ["plugin", "marketplace", "add", "--help"],
        "marketplace_remove": ["plugin", "marketplace", "remove", "--help"],
        "plugin_add": ["plugin", "add", "--help"],
        "plugin_remove": ["plugin", "remove", "--help"],
    }.items():
        probe = _run_codex(args, check=False)
        commands[name] = probe.returncode == 0
    list_error = "" if list_ok else (result.stderr or result.stdout or "codex plugin list failed").strip()
    return {"codex_version": version, "version_ok": version_ok,
            "plugin_list_json": list_ok, "plugin_list_error": list_error[-2000:], "commands": commands,
            "ok": version_ok and list_ok and all(commands.values())}


def _legacy_marketplace_repairable() -> bool:
    """Recognize the exact V6.1-V6.3 managed manifest drift before mutation."""
    try:
        state = load_json(state_path("user"), {})
        manifest = load_json(plugin_marketplace_manifest(), {})
    except Exception:
        return False
    if not isinstance(state, dict) or not isinstance(manifest, dict):
        return False
    if state.get("package") != PACKAGE or state.get("mode") != "plugin":
        return False
    if str(state.get("version") or "") not in {"6.1.0", "6.2.0", "6.3.0"}:
        return False
    if state.get("schema_version") not in {1, 2} or manifest.get("name") != MARKETPLACE:
        return False
    return any(isinstance(item, dict) and item.get("name") == PACKAGE
               for item in manifest.get("plugins", []))


def _require_plugin_host() -> Dict[str, Any]:
    """Fail closed before changing files when the host cannot prove capability."""
    profile = _probe_plugin_host()
    if not profile["version_ok"]:
        raise InstallError("Plugin 模式仅支持 Codex CLI 0.150.1；当前: %s" %
                           (profile["codex_version"] or "未知"))
    if not profile["plugin_list_json"]:
        if not _legacy_marketplace_repairable():
            raise InstallError("codex plugin list --json schema 未知，拒绝 Plugin 安装")
        profile["legacy_marketplace_repair"] = True
        profile["ok"] = profile["version_ok"] and all(profile["commands"].values())
    if not all(profile["commands"].values()):
        raise InstallError("Codex Plugin 子命令能力不完整，拒绝安装: %s" % profile["commands"])
    return profile


def install_user(mode: str, dry_run: bool, force: bool) -> None:
    ch = codex_home(); sh = user_skills_home(); home = Path.home().absolute()
    # 防止误把源码/安装包目录当成 CODEX_HOME 后自覆盖。
    source_root = ROOT.absolute()
    try:
        ch.relative_to(source_root)
        raise InstallError("危险目录：CODEX_HOME 位于 V6 源码/安装包目录内，拒绝自覆盖")
    except ValueError:
        pass
    reject_link_ancestors(ch); reject_link_ancestors(home / ".agents")
    targets: List[Tuple[str, Path]] = [("global", ch / "AGENTS.md"), ("install-state", state_path("user"))]
    targets.extend(("agent:" + p.name, ch / "agents" / p.name) for p in agent_files())
    if mode == "standalone":
        targets.extend(("skill:" + n, sh / n) for n in skill_names())
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
    migrated_old_state = migrate_state_v1_to_v2(old_state, "user", mode)
    if dry_run:
        print(json.dumps({"scope":"user","mode":mode,"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_schema":old_state.get("schema_version"),
                          "state_migration":"v1-to-v2" if old_state.get("schema_version") == 1 else "none",
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
    if mode == "plugin" and shutil.which("codex"):
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
        # global managed block
        gp = ch / "AGENTS.md"; _io_path(gp.parent).mkdir(parents=True, exist_ok=True)
        io_gp = _io_path(gp)
        existing = io_gp.read_text(encoding="utf-8-sig") if io_gp.exists() else ""
        text_atomic(gp, managed_global_text(existing))
        _record_applied(journal, "global", gp)
        # reviewer agents
        for src in agent_files():
            dst = ch / "agents" / src.name; copy_atomic(src, dst); _record_applied(journal, "agent:" + src.name, dst)
        if mode == "standalone":
            for name in skill_names():
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
                marketplace = _merged_marketplace_manifest(load_json(marketplace_path, {}))
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
            _record_mutation_intent(journal, "plugin-cache", plugin_cache_root(),
                                    tree_sha256(plugin_marketplace_payload()))
            _activate_plugin(plugin_marketplace_root())
            _hard_crash("PLUGIN:AFTER_ADD")
            active, detail = _plugin_activation_status(VERSION)
            if not active:
                raise InstallError("Plugin 注册读回未达到 installed=true、enabled=true、version=%s: %s" % (VERSION, detail))
            cache_report = payload_report(plugin_cache_root())
            journal["cache_payload"] = cache_report
            _record_applied(journal, "plugin-cache", plugin_cache_root())
            _hard_crash("PLUGIN:AFTER_CACHE_VERIFY")
        else:
            cache_report = None
        managed = {str(path): tree_sha256(path) for _label, path in targets if _io_path(path).exists() and _label not in {"global", "hooks-json", "install-state"}}
        managed[str(gp)] = hashlib.sha256((ROOT / "global" / "AGENTS.md").read_bytes()).hexdigest()
        state = dict(migrated_old_state)
        state.update({"schema_version":2,"package":PACKAGE,"version":VERSION,"scope":"user","mode":mode,
                      "installed_at":time.time(),"backup":str(backup),"managed_hashes":managed,
                      "previous_backup":old_state.get("backup"),"capability_profile":capability_profile})
        if mode == "plugin":
            source_report = payload_report(ROOT)
            marketplace_report = payload_report(plugin_marketplace_payload())
            state["payload_identity"] = {"manifest_digest":source_report["payload_digest"],
                                         "marketplace_digest":marketplace_report["payload_digest"],
                                         "cache_digest":cache_report["payload_digest"] if cache_report else None,
                                         "file_count":source_report["file_count"]}
            # V6.6 SessionEnd only enqueues a signed job.  Initialize the
            # host-bound keyring before committing installation; existing V6.5
            # keys and all RETIRED verification history are preserved.
            init_keyring()
            state["integrity_keyring"] = verify_keyring()
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
        # 安装事务失败：撤销本次 Plugin 注册、恢复文件/旧状态，再尽力恢复升级前 Plugin。
        _journal_write(journal, "ROLLBACK_STARTED")
        if mode == "plugin" and shutil.which("codex"):
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
        if mode == "plugin" and shutil.which("codex"):
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
    print("[OK] V6.6 账户级安装完成，mode=%s" % mode)
    if mode == "plugin":
        print("[OK] Codex Marketplace 已注册，Plugin 已执行 codex plugin add")


def install_repo(repo_path: str, dry_run: bool) -> None:
    repo = git_root(Path(repo_path))
    root = repo / ".agents" / "skills"
    reject_link_ancestors(root.parent, repo)
    targets = [("skill:" + n, root / n) for n in skill_names()] + [("install-state", state_path("repo", repo))]
    for _label, target in targets:
        ensure_inside(target, repo); reject_link_ancestors(target.parent, repo)
    old_state = load_json(state_path("repo", repo), {}) or {}
    migrated_old_state = migrate_state_v1_to_v2(old_state, "repo", "standalone")
    if dry_run:
        print(json.dumps({"scope":"repo","repo":str(repo),"from_version":old_state.get("version"),
                          "to_version":VERSION,"state_migration":"v1-to-v2" if old_state.get("schema_version") == 1 else "none",
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
        for name in skill_names():
            dst = root / name; copy_atomic(ROOT / "skills" / name, dst); _record_applied(journal, "skill:" + name, dst)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"repo"})
        managed = {str(t):tree_sha256(t) for label,t in targets if label != "install-state"}
        state = dict(migrated_old_state)
        state.update({"schema_version":2,"package":PACKAGE,"version":VERSION,"scope":"repo","mode":"standalone",
                      "repo":str(repo),"backup":str(backup),"previous_backup":old_state.get("backup"),
                      "managed_hashes":managed})
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
    print("[OK] V6.6 仓库级 Skills 安装完成: %s" % repo)


def verify(scope: str, mode: str, repo_path: Optional[str]) -> None:
    errors: List[str] = []
    if scope == "repo":
        repo = git_root(Path(repo_path or ".")); root = repo / ".agents" / "skills"
        for name in skill_names():
            dst=root/name; src=ROOT/"skills"/name
            if not _io_path(dst).is_dir(): errors.append("缺少 %s" % dst)
            elif tree_sha256(dst)!=tree_sha256(src): errors.append("内容漂移 %s" % dst)
    else:
        ch=codex_home()
        if mode == "standalone":
            for name in skill_names():
                dst=user_skills_home()/name; src=ROOT/"skills"/name
                if not _io_path(dst).is_dir(): errors.append("缺少 Skill %s" % name)
                elif tree_sha256(dst)!=tree_sha256(src): errors.append("Skill 漂移 %s" % name)
            if not _io_path(ch/"cp-assistant-hooks"/"cp_hook.py").is_file(): errors.append("缺少 standalone Hook")
        else:
            market = plugin_marketplace_root()
            plugin=market/"plugins"/PACKAGE
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
                state = migrate_state_v1_to_v2(load_json(state_path("user"), {}) or {}, "user", mode)
                identity = state.get("payload_identity") or {}
                if state.get("version") != VERSION or state.get("schema_version") != 2:
                    errors.append("安装状态不是 V6.6 schema 2")
                if any(identity.get(key) != source_report["payload_digest"]
                       for key in ("manifest_digest", "marketplace_digest", "cache_digest")):
                    errors.append("安装状态 payload 身份读回不一致")
            except InstallError as exc:
                errors.append(str(exc))
            try:
                verify_keyring()
            except Exception as exc:
                errors.append("完整性 keyring 不可用: %s" % exc)
        for src in agent_files():
            if not _io_path(ch/"agents"/src.name).is_file(): errors.append("缺少 Reviewer %s" % src.name)
        io_agents = _io_path(ch/"AGENTS.md")
        text=io_agents.read_text(encoding="utf-8-sig") if io_agents.is_file() else ""
        if BEGIN not in text or END not in text: errors.append("缺少全局 AGENTS 受管区块")
    if errors:
        for item in errors: print("[FAIL]",item)
        raise SystemExit(1)
    print("[OK] V6.6 安装验证通过 scope=%s mode=%s" % (scope, mode))


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
            # global 保存的是源区块 hash，整文件天然不同，不做整文件漂移比较。
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
        if shutil.which("codex"):
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
        if shutil.which("codex"):
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
    # V6.6 records its own state file as a transactional target. If an older V6 state existed,
    # the restore loop has put it back; otherwise ensure no current state remains.
    if not previous_state_record:
        _io_path(sp).unlink(missing_ok=True)
    if installed_mode == "plugin" and previous_state.get("mode") == "plugin" and shutil.which("codex") and _io_path(plugin_marketplace_root()).exists():
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
    print("[OK] V6.6 已卸载并恢复安装前状态；项目上下文/观测数据未删除")


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
    # PREPARED is persisted before the backup directory exists.  No managed
    # target has been touched at this point, so recovery is an archive/cleanup.
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
    if scope == "user" and journal.get("mode") == "plugin" and shutil.which("codex"):
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
    active, detail = _plugin_activation_status() if scope == "user" and shutil.which("codex") else (False, "not checked")
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
            "payload_identity": payload,
            "skills": skill_names(), "reviewers": [p.name for p in agent_files()],
            "hooks": str(ch / "hooks.json") if scope == "user" else None}
    print(json.dumps(data, ensure_ascii=False, indent=2))


def doctor(recover: bool = False, scope: str = "user", repo_path: Optional[str] = None) -> None:
    if recover:
        recover_transaction(scope, repo_path)
        return
    codex_exe = shutil.which("codex")
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
    print(json.dumps({
        "package":PACKAGE,"version":VERSION,"target_codex":"0.150.1","python":sys.executable,
        "home":str(Path.home()),"codex_home":str(codex_home()),
        "user_skills_home":str(user_skills_home()),
        "plugin_marketplace_root":str(plugin_marketplace_root()),
        "skill_count":len(skill_names()),"reviewer_count":len(agent_files()),
        "plugin_manifest":str(ROOT/".codex-plugin"/"plugin.json"),
        "hooks_manifest":str(ROOT/"hooks"/"hooks.json"), "transaction": str(transaction_path("user")),
        "payload_manifest":str(ROOT/PAYLOAD_MANIFEST_NAME),
        "plugin_cache_root":str(plugin_cache_root()),
        "git":shutil.which("git"),"codex":codex_exe,"codex_version":codex_version,
        "capability_profile":capability
    },ensure_ascii=False,indent=2))


def main() -> None:
    p=argparse.ArgumentParser(description="Codex 跨项目长期技术助手 V6.6 安装器")
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
