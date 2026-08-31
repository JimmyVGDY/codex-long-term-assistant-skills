#!/usr/bin/env python3
"""V6 安装/验证/卸载器。

设计目标：官方账户 Skill 目录、Plugin-first、standalone 兼容、仓库作用域隔离、
路径逃逸防护、备份、漂移检测与 dry-run。不会自动删除未知使用方资产。
"""
from __future__ import annotations

import argparse
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
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
PACKAGE = "codex-cross-project-engineering-assistant"
VERSION = "6.2.0"
MARKETPLACE = "cp-assistant-local"
BEGIN = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:BEGIN -->"
END = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:END -->"

class InstallError(RuntimeError):
    pass


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


def plugin_payload_source(tmp: Path) -> Path:
    name = PACKAGE
    out = tmp / name
    out.mkdir(parents=True)
    for rel in (".codex-plugin", "skills", "hooks", "runtime"):
        shutil.copytree(_io_path(ROOT / rel), _io_path(out / rel))
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


def _codex_version_text() -> str:
    result = _run_codex(["--version"], check=False)
    return (result.stdout or result.stderr or "").strip()


def _plugin_activation_status() -> Tuple[bool, str]:
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
            ok = bool(item.get("installed", True)) and bool(item.get("enabled", False))
            return ok, json.dumps(item, ensure_ascii=False)
    return False, "未在 Codex installed 列表中发现 %s@%s" % (PACKAGE, MARKETPLACE)


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
        targets.append(("plugin-marketplace", plugin_marketplace_root()))
    for _label, target in targets:
        reject_link_ancestors(target.parent)
    if dry_run:
        print(json.dumps({"scope":"user","mode":mode,"targets":[str(x[1]) for x in targets]}, ensure_ascii=False, indent=2)); return
    backup = backup_root("user"); _io_path(backup).mkdir(parents=True, exist_ok=False)
    records: List[Dict[str, Any]] = []
    previous_plugin_active = False
    previous_market_exists = _io_path(plugin_marketplace_root()).exists() if mode == "plugin" else False
    if mode == "plugin" and shutil.which("codex"):
        try:
            previous_plugin_active, _ = _plugin_activation_status()
        except Exception:
            previous_plugin_active = False
    try:
        for label, target in targets:
            records.append(backup_target(target, backup, label))
        # global managed block
        gp = ch / "AGENTS.md"; _io_path(gp.parent).mkdir(parents=True, exist_ok=True)
        io_gp = _io_path(gp)
        existing = io_gp.read_text(encoding="utf-8-sig") if io_gp.exists() else ""
        text_atomic(gp, managed_global_text(existing))
        # reviewer agents
        for src in agent_files(): copy_atomic(src, ch / "agents" / src.name)
        if mode == "standalone":
            for name in skill_names(): copy_atomic(ROOT / "skills" / name, sh / name)
            copy_atomic(ROOT / "runtime" / "cp_runtime", ch / "runtime" / "cp_runtime")
            copy_atomic(ROOT / "hooks" / "cp_hook.py", ch / "cp-assistant-hooks" / "cp_hook.py")
            merge_hooks(ch / "hooks.json", ch / "cp-assistant-hooks" / "cp_hook.py")
        else:
            market = plugin_marketplace_root()
            if _io_path(market).exists(): remove_path(market)
            _io_path(market / ".agents" / "plugins").mkdir(parents=True, exist_ok=True)
            _io_path(market / "plugins").mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="cp-v6-plugin-") as td:
                src = plugin_payload_source(Path(td))
                copy_atomic(src, market / "plugins" / PACKAGE)
            marketplace = {
                "name": MARKETPLACE,
                "owner": {"name": "local-user"},
                "plugins": [{"name": PACKAGE, "source": {"source": "local", "path": "./plugins/%s" % PACKAGE}, "description": "Codex 跨项目长期技术助手 V6.2"}]
            }
            write_json_atomic(market / ".agents" / "plugins" / "marketplace.json", marketplace)
        managed = {str(path): tree_sha256(path) for _label, path in targets if _io_path(path).exists() and _label not in {"global", "hooks-json", "install-state"}}
        managed[str(gp)] = hashlib.sha256((ROOT / "global" / "AGENTS.md").read_bytes()).hexdigest()
        state = {"schema_version":1,"package":PACKAGE,"version":VERSION,"scope":"user","mode":mode,"installed_at":time.time(),"backup":str(backup),"managed_hashes":managed}
        write_json_atomic(state_path("user"), state)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"user","mode":mode})
        if mode == "plugin":
            _activate_plugin(plugin_marketplace_root())
    except Exception:
        # 安装事务失败：撤销本次 Plugin 注册、恢复文件/旧状态，再尽力恢复升级前 Plugin。
        if mode == "plugin" and shutil.which("codex"):
            try:
                _deactivate_plugin(check=False)
            except Exception:
                pass
        for record in reversed(records):
            target = Path(record["target"])
            try:
                io_target = _io_path(target)
                if io_target.exists() or io_target.is_symlink(): remove_path(target)
                if record.get("existed"):
                    src = backup / record["backup_relative"]
                    copy_atomic(src, target)
            except Exception:
                pass
        if mode == "plugin" and shutil.which("codex"):
            if not previous_market_exists:
                try:
                    _remove_marketplace(check=False)
                except Exception:
                    pass
            if previous_plugin_active and _io_path(plugin_marketplace_root()).exists():
                try:
                    _activate_plugin(plugin_marketplace_root())
                except Exception:
                    pass
        raise
    print("[OK] V6.2 账户级安装完成，mode=%s" % mode)
    if mode == "plugin":
        print("[OK] Codex Marketplace 已注册，Plugin 已执行 codex plugin add")


def install_repo(repo_path: str, dry_run: bool) -> None:
    repo = git_root(Path(repo_path))
    root = repo / ".agents" / "skills"
    reject_link_ancestors(root.parent, repo)
    targets = [("skill:" + n, root / n) for n in skill_names()]
    for _label, target in targets:
        ensure_inside(target, repo); reject_link_ancestors(target.parent, repo)
    if dry_run:
        print(json.dumps({"scope":"repo","repo":str(repo),"targets":[str(t) for _,t in targets]}, ensure_ascii=False, indent=2)); return
    backup = backup_root("repo", repo); _io_path(backup).mkdir(parents=True, exist_ok=False)
    records = [backup_target(target, backup, label) for label, target in targets]
    try:
        for name in skill_names(): copy_atomic(ROOT / "skills" / name, root / name)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"repo"})
        write_json_atomic(state_path("repo", repo), {"schema_version":1,"package":PACKAGE,"version":VERSION,"scope":"repo","repo":str(repo),"backup":str(backup),"managed_hashes":{str(t):tree_sha256(t) for _,t in targets}})
    except Exception:
        for record in reversed(records):
            target=Path(record["target"])
            try:
                io_target = _io_path(target)
                if io_target.exists() or io_target.is_symlink(): remove_path(target)
                if record.get("existed"): copy_atomic(backup / record["backup_relative"], target)
            except Exception: pass
        raise
    print("[OK] V6.2 仓库级 Skills 安装完成: %s" % repo)


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
                    if os.name == "nt" and not any(command.startswith("cmd.exe /d /c ") and '"' not in command for command in commands):
                        errors.append("Windows Hook 启动命令与 Codex 0.150.1 不兼容 %s" % hook_name)
            active, detail = _plugin_activation_status()
            if not active: errors.append("Plugin 未被 Codex 实际安装并启用: %s" % detail)
        for src in agent_files():
            if not _io_path(ch/"agents"/src.name).is_file(): errors.append("缺少 Reviewer %s" % src.name)
        io_agents = _io_path(ch/"AGENTS.md")
        text=io_agents.read_text(encoding="utf-8-sig") if io_agents.is_file() else ""
        if BEGIN not in text or END not in text: errors.append("缺少全局 AGENTS 受管区块")
    if errors:
        for item in errors: print("[FAIL]",item)
        raise SystemExit(1)
    print("[OK] V6.2 安装验证通过 scope=%s mode=%s" % (scope, mode))


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
    previous_market_record = next((r for r in records if r.get("label") == "plugin-marketplace"), None)
    previous_state_record = next((r for r in records if r.get("label") == "install-state"), None)
    previous_state = {}
    if previous_state_record and previous_state_record.get("existed") and previous_state_record.get("backup_relative"):
        previous_state = load_json(backup / previous_state_record["backup_relative"], {}) or {}
    if dry_run:
        print(json.dumps({"restore_backup":str(backup),"records":records,"installed_mode":installed_mode},ensure_ascii=False,indent=2)); return
    if installed_mode == "plugin":
        if shutil.which("codex"):
            try:
                _deactivate_plugin(check=not force)
                if not (previous_market_record and previous_market_record.get("existed")):
                    _remove_marketplace(check=not force)
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
        previous = backup / record["backup_relative"] if record.get("existed") and record.get("backup_relative") else None
        if target.name == "hooks.json" and scope == "user":
            restore_managed_hooks(target, previous)
            continue
        if target.name == "AGENTS.md" and scope == "user":
            restore_global_agents(target, previous)
            continue
        io_target = _io_path(target)
        if io_target.exists() or io_target.is_symlink(): remove_path(target)
        if record.get("existed"):
            src=backup/record["backup_relative"]
            if tree_sha256(src)!=record.get("sha256"): raise InstallError("备份完整性失败: %s" % src)
            copy_atomic(src,target)
    # V6.2 records its own state file as a transactional target. If an older V6 state existed,
    # the restore loop has put it back; otherwise ensure no current state remains.
    if not previous_state_record:
        _io_path(sp).unlink(missing_ok=True)
    if installed_mode == "plugin" and previous_state.get("mode") == "plugin" and shutil.which("codex") and _io_path(plugin_marketplace_root()).exists():
        try:
            _activate_plugin(plugin_marketplace_root())
        except Exception as exc:
            if not force:
                raise InstallError("已恢复旧版文件，但旧 Plugin 重新激活失败: %s" % exc)
            print("[WARN] --force：旧版 Plugin 文件已恢复，但未能重新激活")
    print("[OK] V6.2 已卸载并恢复安装前状态；项目上下文/观测数据未删除")


def doctor() -> None:
    codex_exe = shutil.which("codex")
    codex_version = None
    if codex_exe:
        try:
            codex_version = _codex_version_text()
        except Exception:
            codex_version = None
    print(json.dumps({
        "package":PACKAGE,"version":VERSION,"target_codex":"0.150.1","python":sys.executable,
        "home":str(Path.home()),"codex_home":str(codex_home()),
        "user_skills_home":str(user_skills_home()),
        "plugin_marketplace_root":str(plugin_marketplace_root()),
        "skill_count":len(skill_names()),"reviewer_count":len(agent_files()),
        "plugin_manifest":str(ROOT/".codex-plugin"/"plugin.json"),
        "hooks_manifest":str(ROOT/"hooks"/"hooks.json"),
        "git":shutil.which("git"),"codex":codex_exe,"codex_version":codex_version
    },ensure_ascii=False,indent=2))


def main() -> None:
    p=argparse.ArgumentParser(description="Codex 跨项目长期技术助手 V6.2 安装器")
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("install","verify","uninstall"):
        q=sub.add_parser(name)
        q.add_argument("--scope",choices=["user","repo"],default="user")
        q.add_argument("--mode",choices=["plugin","standalone"],default="plugin")
        q.add_argument("--repo-path")
        if name in {"install","uninstall"}: q.add_argument("--dry-run",action="store_true")
        if name in {"install","uninstall"}: q.add_argument("--force",action="store_true")
    sub.add_parser("doctor")
    args=p.parse_args()
    if args.command=="doctor": doctor(); return
    if args.command=="install":
        if args.scope=="repo": install_repo(args.repo_path or ".",args.dry_run)
        else: install_user(args.mode,args.dry_run,args.force)
    elif args.command=="verify": verify(args.scope,args.mode,args.repo_path)
    elif args.command=="uninstall": uninstall(args.scope,args.mode,args.repo_path,args.force,args.dry_run)

if __name__=="__main__":
    try: main()
    except InstallError as exc:
        print("[ERROR]",exc,file=sys.stderr); raise SystemExit(2)
