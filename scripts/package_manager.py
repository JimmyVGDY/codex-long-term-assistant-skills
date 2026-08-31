#!/usr/bin/env python3
"""V6 安装/验证/卸载器。

设计目标：官方用户 Skill 目录、Plugin-first、standalone 兼容、仓库作用域隔离、
路径逃逸防护、备份、漂移检测与 dry-run。不会自动删除未知用户资产。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
PACKAGE = "codex-cross-project-engineering-assistant"
BEGIN = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:BEGIN -->"
END = "<!-- CODEX-CROSS-PROJECT-ASSISTANT:END -->"

class InstallError(RuntimeError):
    pass


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    for item in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel = item.relative_to(path).as_posix()
        h.update(rel.encode("utf-8")); h.update(b"\0")
        h.update(sha256_file(item).encode("ascii")); h.update(b"\n")
    return h.hexdigest()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser().absolute()


def user_skills_home() -> Path:
    # Codex 当前用户级 Skills 规范目录，不随 CODEX_HOME 改写。
    return (Path.home() / ".agents" / "skills").expanduser().absolute()


def _is_reparse(path: Path) -> bool:
    try:
        st = path.lstat()
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
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], text=True, capture_output=True, check=True, timeout=10)
    except Exception as exc:
        raise InstallError("repo-path 必须位于可识别的 Git 仓库中") from exc
    root = Path(result.stdout.strip()).absolute()
    reject_link_ancestors(root)
    return root


def remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def copy_atomic(src: Path, dst: Path) -> None:
    reject_link_ancestors(dst.parent)
    dst.parent.mkdir(parents=True, exist_ok=True)
    reject_link_ancestors(dst.parent)
    tmp = Path(tempfile.mkdtemp(prefix=dst.name + ".tmp-", dir=str(dst.parent)))
    try:
        staged = tmp / "payload"
        if src.is_dir():
            shutil.copytree(src, staged, symlinks=False)
        else:
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, staged)
        if dst.exists() or dst.is_symlink():
            remove_path(dst)
        os.replace(str(staged), str(dst))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def backup_target(path: Path, backup_root: Path, label: str) -> Dict[str, Any]:
    record: Dict[str, Any] = {"target": str(path), "label": label, "existed": bool(path.exists() or path.is_symlink())}
    if not record["existed"]:
        return record
    if _is_reparse(path):
        raise InstallError("拒绝备份并覆盖链接型目标: %s" % path)
    rel = "items/%03d-%s" % (len(list((backup_root / "items").glob("*"))) if (backup_root / "items").exists() else 0, re.sub(r"[^A-Za-z0-9._-]+", "-", label)[:60])
    out = backup_root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        shutil.copytree(path, out)
        record["kind"] = "directory"
    else:
        shutil.copy2(path, out)
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
        "SessionEnd": [{"hooks": [{"type": "command", "command": command, "timeout": 5}]}],
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
    marker = "cp-assistant-hooks"
    for event, entries in list(hooks.items()):
        if isinstance(entries, list):
            kept = []
            for entry in entries:
                raw = json.dumps(entry, ensure_ascii=False)
                if marker not in raw:
                    kept.append(entry)
            hooks[event] = kept
    for event, entries in fragment.items():
        hooks.setdefault(event, []).extend(entries)
    write_json_atomic(path, data)


def remove_managed_hooks(path: Path) -> None:
    if not path.is_file(): return
    data = load_json(path, {}) or {}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict): return
    marker = "cp-assistant-hooks"
    for event, entries in list(hooks.items()):
        if isinstance(entries, list):
            hooks[event] = [entry for entry in entries if marker not in json.dumps(entry, ensure_ascii=False)]
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
        shutil.copytree(ROOT / rel, out / rel)
    return out


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
    targets: List[Tuple[str, Path]] = [("global", ch / "AGENTS.md")]
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
    backup = backup_root("user"); backup.mkdir(parents=True, exist_ok=False)
    records: List[Dict[str, Any]] = []
    try:
        for label, target in targets:
            records.append(backup_target(target, backup, label))
        # global managed block
        gp = ch / "AGENTS.md"; gp.parent.mkdir(parents=True, exist_ok=True)
        existing = gp.read_text(encoding="utf-8-sig") if gp.exists() else ""
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
            if market.exists(): remove_path(market)
            (market / ".codex-plugin").mkdir(parents=True, exist_ok=True)
            (market / "plugins").mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="cp-v6-plugin-") as td:
                src = plugin_payload_source(Path(td))
                copy_atomic(src, market / "plugins" / PACKAGE)
            marketplace = {
                "name": "cp-assistant-local",
                "owner": {"name": "local-user"},
                "plugins": [{"name": PACKAGE, "source": {"source": "local", "path": "./plugins/%s" % PACKAGE}, "description": "Codex 跨项目长期技术助手 V6"}]
            }
            write_json_atomic(market / ".codex-plugin" / "marketplace.json", marketplace)
        managed = {str(path): tree_sha256(path) for _label, path in targets if path.exists() and _label != "global" and _label != "hooks-json"}
        managed[str(gp)] = hashlib.sha256((ROOT / "global" / "AGENTS.md").read_bytes()).hexdigest()
        state = {"schema_version":1,"package":PACKAGE,"version":"6.0.0","scope":"user","mode":mode,"installed_at":time.time(),"backup":str(backup),"managed_hashes":managed}
        write_json_atomic(state_path("user"), state)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"user","mode":mode})
    except Exception:
        # 安装事务失败时恢复已备份目标。
        for record in reversed(records):
            target = Path(record["target"])
            try:
                if target.exists() or target.is_symlink(): remove_path(target)
                if record.get("existed"):
                    src = backup / record["backup_relative"]
                    copy_atomic(src, target)
            except Exception:
                pass
        raise
    print("[OK] V6 用户级安装完成，mode=%s" % mode)
    if mode == "plugin":
        print("[NEXT] 在 Codex 中注册本地 Marketplace（如尚未注册）：codex plugin marketplace add \"%s\"" % plugin_marketplace_root())
        print("[NEXT] 然后安装插件：codex plugin install %s@cp-assistant-local" % PACKAGE)


def install_repo(repo_path: str, dry_run: bool) -> None:
    repo = git_root(Path(repo_path))
    root = repo / ".agents" / "skills"
    reject_link_ancestors(root.parent, repo)
    targets = [("skill:" + n, root / n) for n in skill_names()]
    for _label, target in targets:
        ensure_inside(target, repo); reject_link_ancestors(target.parent, repo)
    if dry_run:
        print(json.dumps({"scope":"repo","repo":str(repo),"targets":[str(t) for _,t in targets]}, ensure_ascii=False, indent=2)); return
    backup = backup_root("repo", repo); backup.mkdir(parents=True, exist_ok=False)
    records = [backup_target(target, backup, label) for label, target in targets]
    try:
        for name in skill_names(): copy_atomic(ROOT / "skills" / name, root / name)
        write_json_atomic(backup / "backup-manifest.json", {"records":records,"scope":"repo"})
        write_json_atomic(state_path("repo", repo), {"schema_version":1,"package":PACKAGE,"version":"6.0.0","scope":"repo","repo":str(repo),"backup":str(backup),"managed_hashes":{str(t):tree_sha256(t) for _,t in targets}})
    except Exception:
        for record in reversed(records):
            target=Path(record["target"])
            try:
                if target.exists() or target.is_symlink(): remove_path(target)
                if record.get("existed"): copy_atomic(backup / record["backup_relative"], target)
            except Exception: pass
        raise
    print("[OK] V6 仓库级 Skills 安装完成: %s" % repo)


def verify(scope: str, mode: str, repo_path: Optional[str]) -> None:
    errors: List[str] = []
    if scope == "repo":
        repo = git_root(Path(repo_path or ".")); root = repo / ".agents" / "skills"
        for name in skill_names():
            dst=root/name; src=ROOT/"skills"/name
            if not dst.is_dir(): errors.append("缺少 %s" % dst)
            elif tree_sha256(dst)!=tree_sha256(src): errors.append("内容漂移 %s" % dst)
    else:
        ch=codex_home()
        if mode == "standalone":
            for name in skill_names():
                dst=user_skills_home()/name; src=ROOT/"skills"/name
                if not dst.is_dir(): errors.append("缺少 Skill %s" % name)
                elif tree_sha256(dst)!=tree_sha256(src): errors.append("Skill 漂移 %s" % name)
            if not (ch/"cp-assistant-hooks"/"cp_hook.py").is_file(): errors.append("缺少 standalone Hook")
        else:
            plugin=plugin_marketplace_root()/"plugins"/PACKAGE
            if not (plugin/".codex-plugin"/"plugin.json").is_file(): errors.append("缺少 Plugin")
            if not (plugin/"hooks"/"hooks.json").is_file(): errors.append("缺少 Plugin Hooks")
        for src in agent_files():
            if not (ch/"agents"/src.name).is_file(): errors.append("缺少 Reviewer %s" % src.name)
        text=(ch/"AGENTS.md").read_text(encoding="utf-8-sig") if (ch/"AGENTS.md").is_file() else ""
        if BEGIN not in text or END not in text: errors.append("缺少全局 AGENTS 受管区块")
    if errors:
        for item in errors: print("[FAIL]",item)
        raise SystemExit(1)
    print("[OK] V6 安装验证通过 scope=%s mode=%s" % (scope, mode))


def uninstall(scope: str, mode: str, repo_path: Optional[str], force: bool, dry_run: bool) -> None:
    repo = git_root(Path(repo_path or ".")) if scope == "repo" else None
    sp = state_path(scope, repo)
    state = load_json(sp, {}) or {}
    if not state:
        raise InstallError("未找到 V6 安装状态文件；为避免误删未知资产，拒绝无状态卸载")
    hashes = state.get("managed_hashes") or {}
    drift = []
    for raw, expected in hashes.items():
        path=Path(raw)
        if path.exists() and str(expected) not in {"", "missing"} and tree_sha256(path)!=expected:
            # global 保存的是源区块 hash，整文件天然不同，不做整文件漂移比较。
            if path.name != "AGENTS.md": drift.append(str(path))
    if drift and not force:
        raise InstallError("检测到用户修改，拒绝覆盖式卸载；确认后使用 --force：%s" % drift)
    backup = Path(state.get("backup") or "")
    manifest_data = load_json(backup / "backup-manifest.json", {}) or {}
    records = manifest_data.get("records") or []
    if dry_run:
        print(json.dumps({"restore_backup":str(backup),"records":records},ensure_ascii=False,indent=2)); return
    for record in reversed(records):
        target=Path(record["target"])
        if target.name == "hooks.json" and scope == "user" and not record.get("existed"):
            remove_managed_hooks(target)
            if target.is_file() and (load_json(target,{}) or {}).get("hooks") == {}: target.unlink(missing_ok=True)
            continue
        if target.name == "AGENTS.md" and scope == "user" and not record.get("existed"):
            if target.is_file():
                text=target.read_text(encoding="utf-8-sig")
                text=re.sub(r"\n?"+re.escape(BEGIN)+r".*?"+re.escape(END)+r"\n?","\n",text,flags=re.S)
                text_atomic(target,text.strip()+"\n" if text.strip() else "")
            continue
        if target.exists() or target.is_symlink(): remove_path(target)
        if record.get("existed"):
            src=backup/record["backup_relative"]
            if tree_sha256(src)!=record.get("sha256"): raise InstallError("备份完整性失败: %s" % src)
            copy_atomic(src,target)
    sp.unlink(missing_ok=True)
    print("[OK] V6 已卸载并恢复安装前状态；项目上下文/观测数据未删除")


def doctor() -> None:
    print(json.dumps({
        "package":PACKAGE,"version":"6.0.0","python":sys.executable,
        "home":str(Path.home()),"codex_home":str(codex_home()),
        "user_skills_home":str(user_skills_home()),
        "plugin_marketplace_root":str(plugin_marketplace_root()),
        "skill_count":len(skill_names()),"reviewer_count":len(agent_files()),
        "plugin_manifest":str(ROOT/".codex-plugin"/"plugin.json"),
        "hooks_manifest":str(ROOT/"hooks"/"hooks.json"),
        "git":shutil.which("git"),"codex":shutil.which("codex")
    },ensure_ascii=False,indent=2))


def main() -> None:
    p=argparse.ArgumentParser(description="Codex 跨项目长期技术助手 V6 安装器")
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
