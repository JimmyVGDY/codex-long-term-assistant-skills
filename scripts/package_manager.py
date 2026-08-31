#!/usr/bin/env python3
"""V5.1 safe install/verify/doctor/uninstall/restore manager for Codex."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_ROOT = ROOT / "runtime"
if str(_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_ROOT))

from cp_runtime.common import (  # noqa: E402
    RuntimeContractError,
    atomic_write_json,
    atomic_write_text,
    inside,
    read_json,
    tree_sha256,
)

PLATFORM = "codex"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
SKILLS = [item["name"] for item in MANIFEST["skills"]]
DEPRECATED = MANIFEST.get("deprecated_skills", [])
BEGIN = "<!-- codex-cross-project-assistant:begin -->"
END = "<!-- codex-cross-project-assistant:end -->"
LEGACY_BEGIN = BEGIN
LEGACY_END = END
RUNTIME_SOURCE = ROOT / "runtime" / "cp_runtime"
TOOL_SOURCE = ROOT / "scripts" / "cp-runtime.py"
EVOLUTION_TOOL_SOURCE = ROOT / "scripts" / "evolution.py"


def lexical(path: Path) -> Path:
    """Return an absolute normalized path without following the final symlink."""
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def home_paths() -> Tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    home = Path.home().expanduser().resolve()
    app = Path(os.environ.get("CODEX_HOME") or (home / ".codex")).expanduser().resolve()
    skills = app / "skills"
    agents = app / "agents"
    global_file = app / "AGENTS.md"
    runtime_target = app / "runtime" / "cp_runtime"
    tool_target = app / "tools" / "cp-runtime.py"
    legacy = home / ".agents" / "skills"
    backups = home / ".codex-skill-backups"
    return app, skills, agents, global_file, runtime_target, tool_target, legacy, backups


def assert_safe_app(app: Path) -> None:
    home = Path.home().expanduser().resolve()
    resolved = app.resolve()
    forbidden = {Path(resolved.anchor).resolve(), home, ROOT.resolve(), ROOT.parent.resolve()}
    if resolved in forbidden:
        raise RuntimeContractError("CODEX_HOME 指向危险目录: " + str(resolved))
    if inside(ROOT.resolve(), resolved) or inside(resolved, ROOT.resolve()):
        raise RuntimeContractError("CODEX_HOME 不能与安装包源码目录互为父子路径")
    if len(resolved.parts) < 3:
        raise RuntimeContractError("CODEX_HOME 路径过浅，拒绝执行文件替换")


def source_agents_dir() -> Path:
    return ROOT / "custom-agents"


def _managed_targets() -> List[Path]:
    app, skills, agents, global_file, runtime_target, tool_target, legacy, _backups = home_paths()
    targets: List[Path] = [global_file, runtime_target, tool_target, app / "tools" / "evolution.py"]
    targets.extend(skills / name for name in SKILLS + DEPRECATED)
    targets.extend(legacy / name for name in SKILLS + DEPRECATED)
    targets.extend(
        agents / item.name
        for item in source_agents_dir().iterdir()
        if item.is_file() and item.name.lower() != "readme.md"
    )
    return [lexical(path) for path in targets]


def _assert_no_symlink_path(target: Path) -> None:
    app, _skills, _agents, _global, _runtime, _tool, legacy, _backups = home_paths()
    candidate = lexical(target)
    if candidate.is_symlink():
        raise RuntimeContractError("受管目标本身是符号链接，拒绝跟随或替换: " + str(candidate))
    roots = [lexical(app), lexical(legacy)]
    for root in roots:
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        cursor = root
        if cursor.is_symlink():
            raise RuntimeContractError("受管根路径是符号链接: " + str(cursor))
        for part in relative.parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink():
                raise RuntimeContractError("受管目标父路径包含符号链接: " + str(cursor))
        return


def _assert_known_target(target: Path) -> None:
    candidate = lexical(target)
    if candidate not in set(_managed_targets()):
        raise RuntimeContractError("目标不在 V5.1 受管资源清单中: " + str(target))
    _assert_no_symlink_path(candidate)


def planned_operations(component: str) -> List[Tuple[str, str]]:
    app, skills, agents, global_file, runtime_target, tool_target, legacy, _backups = home_paths()
    assert_safe_app(app)
    operations: List[Tuple[str, str]] = []
    if component in {"all", "global"}:
        operations.append(("merge-global", str(global_file)))
    if component in {"all", "skills"}:
        operations.append(("replace-runtime", str(runtime_target)))
        operations.append(("replace-tool", str(tool_target)))
        operations.append(("replace-evolution-tool", str(app / "tools" / "evolution.py")))
        for name in DEPRECATED:
            operations.append(("remove-deprecated", str(skills / name)))
        for name in SKILLS:
            operations.append(("replace-skill", str(skills / name)))
        for name in SKILLS + DEPRECATED:
            if (legacy / name).exists():
                operations.append(("remove-legacy-duplicate", str(legacy / name)))
    if component in {"all", "agents"}:
        for item in source_agents_dir().iterdir():
            if item.is_file() and item.name.lower() != "readme.md":
                operations.append(("replace-agent", str(agents / item.name)))
    return operations


def remove_path(target: Path) -> None:
    _assert_known_target(target)
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def copy_file_atomic(source: Path, target: Path) -> None:
    _assert_known_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + target.name + ".", dir=str(target.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def copy_tree_atomic(source: Path, target: Path) -> None:
    _assert_known_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path(tempfile.mkdtemp(prefix="." + target.name + ".", dir=str(target.parent)))
    try:
        shutil.rmtree(temp_path)
        shutil.copytree(source, temp_path, symlinks=True)
        if target.exists() or target.is_symlink():
            remove_path(target)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)


def backup_path(source: Path, backup_root: Path, relative: str, records: List[Dict[str, Any]]) -> None:
    _assert_known_target(source)
    target = backup_root / relative
    existed = source.exists() or source.is_symlink()
    record: Dict[str, Any] = {
        "target": str(lexical(source)),
        "backup_relative": relative,
        "existed": existed,
        "kind": "missing",
        "sha256": None,
    }
    if existed:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, target, symlinks=True)
            record["kind"] = "directory"
        else:
            shutil.copy2(source, target, follow_symlinks=False)
            record["kind"] = "file"
        record["sha256"] = tree_sha256(target)
    records.append(record)


def merge_global(target: Path, source: Path, force: bool = False) -> None:
    _assert_known_target(target)
    managed = source.read_text(encoding="utf-8-sig").strip()
    if force or not target.exists():
        atomic_write_text(target, managed + "\n")
        return
    existing = target.read_text(encoding="utf-8-sig")
    existing = existing.replace(LEGACY_BEGIN, BEGIN).replace(LEGACY_END, END)
    begin_count = existing.count(BEGIN)
    end_count = existing.count(END)
    if begin_count != end_count or begin_count > 1:
        raise RuntimeContractError("全局受管标记异常")
    if begin_count == 0:
        result = existing.rstrip() + "\n\n" + managed + "\n"
    else:
        result = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), managed, existing, count=1, flags=re.S)
    atomic_write_text(target, result)


def command_install(args: argparse.Namespace) -> None:
    app, skills, agents, global_file, runtime_target, tool_target, legacy, backups = home_paths()
    try:
        assert_safe_app(app)
        operations = planned_operations(args.component)
    except RuntimeContractError as exc:
        die(str(exc))
    for operation, path in operations:
        print(f"{operation}: {path}")
    if args.dry_run:
        print("[DRY-RUN] 未修改文件")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = backups / timestamp
    sequence = 1
    while backup_root.exists():
        backup_root = backups / (timestamp + "-{:02d}".format(sequence))
        sequence += 1
    records: List[Dict[str, Any]] = []
    app.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=False)

    try:
        if args.component in {"all", "global"}:
            backup_path(global_file, backup_root, "global/" + global_file.name, records)
            merge_global(global_file, ROOT / "global" / global_file.name, args.force_replace_global)

        if args.component in {"all", "skills"}:
            backup_path(runtime_target, backup_root, "runtime/cp_runtime", records)
            copy_tree_atomic(RUNTIME_SOURCE, runtime_target)
            backup_path(tool_target, backup_root, "tools/cp-runtime.py", records)
            copy_file_atomic(TOOL_SOURCE, tool_target)
            evolution_tool_target = app / "tools" / "evolution.py"
            backup_path(evolution_tool_target, backup_root, "tools/evolution.py", records)
            copy_file_atomic(EVOLUTION_TOOL_SOURCE, evolution_tool_target)
            skills.mkdir(parents=True, exist_ok=True)
            for name in DEPRECATED:
                target = skills / name
                backup_path(target, backup_root, "deprecated-skills/" + name, records)
                if target.exists() or target.is_symlink():
                    remove_path(target)
            for name in SKILLS + DEPRECATED:
                target = legacy / name
                if target.exists() or target.is_symlink():
                    backup_path(target, backup_root, "legacy-skills/" + name, records)
                    remove_path(target)
            for name in SKILLS:
                target = skills / name
                backup_path(target, backup_root, "skills/" + name, records)
                copy_tree_atomic(ROOT / "skills" / name, target)

        if args.component in {"all", "agents"}:
            agents.mkdir(parents=True, exist_ok=True)
            for item in source_agents_dir().iterdir():
                if not item.is_file() or item.name.lower() == "readme.md":
                    continue
                target = agents / item.name
                backup_path(target, backup_root, "agents/" + item.name, records)
                copy_file_atomic(item, target)

        backup_manifest = {
            "schema_version": 2,
            "platform": PLATFORM,
            "package_version": MANIFEST["version"],
            "created_at": timestamp,
            "codex_home": str(app),
            "records": records,
        }
        atomic_write_json(backup_root / "backup-manifest.json", backup_manifest, seal=True)
        install_state = {
            "version": MANIFEST["version"],
            "release_name": MANIFEST["release_name"],
            "installed_at": timestamp,
            "skills_home": str(skills),
            "runtime_home": str(runtime_target),
            "tool": str(tool_target),
            "evolution_tool": str(app / "tools" / "evolution.py"),
            "backup": str(backup_root),
        }
        atomic_write_json(app / ".cross-project-assistant-install.json", install_state)
    except Exception:
        # Leave the complete backup for explicit recovery; never hide a partial installation.
        print("[WARN] 安装中断，备份保留于: " + str(backup_root), file=sys.stderr)
        raise
    print("[OK] 安装完成，备份:", backup_root)


def collect_verification_errors() -> List[str]:
    app, skills, agents, global_file, runtime_target, tool_target, legacy, _backups = home_paths()
    errors: List[str] = []
    try:
        assert_safe_app(app)
    except RuntimeContractError as exc:
        errors.append(str(exc))
        return errors
    if not global_file.is_file():
        errors.append("缺少全局文件")
    else:
        text = global_file.read_text(encoding="utf-8-sig")
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            errors.append("受管标记不是一份")
    if not (runtime_target / "__init__.py").is_file() or not (runtime_target / "cli.py").is_file():
        errors.append("缺少 cp_runtime")
    elif tree_sha256(runtime_target) != tree_sha256(RUNTIME_SOURCE):
        errors.append("cp_runtime 内容与安装包不一致")
    if not tool_target.is_file():
        errors.append("缺少 cp-runtime.py")
    elif tree_sha256(tool_target) != tree_sha256(TOOL_SOURCE):
        errors.append("cp-runtime.py 内容与安装包不一致")
    evolution_tool_target = app / "tools" / "evolution.py"
    if not evolution_tool_target.is_file():
        errors.append("缺少 evolution.py")
    elif tree_sha256(evolution_tool_target) != tree_sha256(EVOLUTION_TOOL_SOURCE):
        errors.append("evolution.py 内容与安装包不一致")
    for name in SKILLS:
        target = skills / name
        source = ROOT / "skills" / name
        if not (target / "SKILL.md").is_file():
            errors.append("缺少 Skill " + name)
        elif tree_sha256(target) != tree_sha256(source):
            errors.append("Skill 内容与安装包不一致 " + name)
    for name in DEPRECATED:
        if (skills / name).exists():
            errors.append("残留废弃 Skill " + name)
    for name in SKILLS + DEPRECATED:
        if (legacy / name).exists():
            errors.append("旧路径存在同名 Skill " + str(legacy / name))
    for item in source_agents_dir().iterdir():
        if not item.is_file() or item.name.lower() == "readme.md":
            continue
        target = agents / item.name
        if not target.is_file():
            errors.append("缺少 Agent " + item.name)
        elif tree_sha256(target) != tree_sha256(item):
            errors.append("Agent 内容与安装包不一致 " + item.name)
    return errors


def command_verify(_args: argparse.Namespace) -> None:
    errors = collect_verification_errors()
    if errors:
        for item in errors:
            print("[FAIL]", item)
        raise SystemExit(1)
    print("[OK] 用户级安装验证通过")


def command_doctor(_args: argparse.Namespace) -> None:
    app, skills, agents, global_file, runtime_target, tool_target, legacy, backups = home_paths()
    print("# Doctor")
    print("platform:", PLATFORM)
    print("app_home:", app)
    print("skills_home:", skills)
    print("agents_home:", agents)
    print("global:", global_file)
    print("runtime:", runtime_target)
    print("tool:", tool_target)
    print("evolution_tool:", app / "tools" / "evolution.py")
    print("project_context_root:", app / "project-context")
    print("version:", MANIFEST["version"])
    print("global_exists:", global_file.exists())
    print("skills_found:", sum((skills / name / "SKILL.md").is_file() for name in SKILLS), "/", len(SKILLS))
    print("runtime_exists:", (runtime_target / "cli.py").is_file())
    print("deprecated_present:", [name for name in DEPRECATED if (skills / name).exists()])
    print("legacy_duplicates:", [name for name in SKILLS if (legacy / name).exists()])
    print("python:", sys.executable)
    print("git:", shutil.which("git") or "missing")
    print("backups:", backups)
    print("verification_errors:", collect_verification_errors())


def remove_managed_global(global_file: Path) -> None:
    _assert_known_target(global_file)
    if not global_file.exists():
        return
    text = global_file.read_text(encoding="utf-8-sig")
    text = text.replace(LEGACY_BEGIN, BEGIN).replace(LEGACY_END, END)
    text = re.sub(r"\n?" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "\n", text, flags=re.S)
    atomic_write_text(global_file, text.strip() + "\n" if text.strip() else "")


def command_uninstall(args: argparse.Namespace) -> None:
    app, skills, agents, global_file, runtime_target, tool_target, _legacy, _backups = home_paths()
    try:
        assert_safe_app(app)
    except RuntimeContractError as exc:
        die(str(exc))
    if args.dry_run:
        for _operation, path in planned_operations(args.component):
            print("remove-managed:", path)
        print("[DRY-RUN] 未修改文件")
        return
    if args.component in {"all", "global"}:
        remove_managed_global(global_file)
    if args.component in {"all", "skills"}:
        for name in SKILLS + DEPRECATED:
            target = skills / name
            if target.exists() or target.is_symlink():
                remove_path(target)
        for target in (runtime_target, tool_target, app / "tools" / "evolution.py"):
            if target.exists() or target.is_symlink():
                remove_path(target)
    if args.component in {"all", "agents"}:
        for item in source_agents_dir().iterdir():
            target = agents / item.name
            if item.is_file() and item.name.lower() != "readme.md" and target.exists():
                remove_path(target)
    print("[OK] 已卸载本包受管资源；项目上下文未自动删除")


def _safe_backup_root(requested: Optional[str], backups: Path) -> Path:
    candidates = sorted(path for path in backups.glob("*") if (path / "backup-manifest.json").is_file())
    if requested:
        chosen = Path(requested).expanduser().resolve()
    else:
        if not candidates:
            raise RuntimeContractError("没有可恢复备份")
        chosen = candidates[-1].resolve()
    if not inside(chosen, backups.resolve()):
        raise RuntimeContractError("备份目录不在受管 backups 根目录下")
    if not (chosen / "backup-manifest.json").is_file():
        raise RuntimeContractError("备份缺少 backup-manifest.json")
    return chosen


def command_restore(args: argparse.Namespace) -> None:
    app, _skills, _agents, _global_file, _runtime_target, _tool_target, _legacy, backups = home_paths()
    try:
        assert_safe_app(app)
        backup_root = _safe_backup_root(args.backup, backups)
        manifest = read_json(backup_root / "backup-manifest.json", verify=True, label="Backup Manifest")
    except RuntimeContractError as exc:
        die(str(exc))
    if manifest.get("platform") != PLATFORM or manifest.get("codex_home") != str(app):
        die("备份不属于当前 Codex Home")
    print("restore from", backup_root)
    for record in manifest.get("records", []):
        try:
            target = lexical(Path(record["target"]))
            _assert_known_target(target)
            source = (backup_root / record["backup_relative"]).resolve()
            if not inside(source, backup_root):
                raise RuntimeContractError("备份文件路径越界")
            if record.get("existed"):
                if not source.exists() and not source.is_symlink():
                    raise RuntimeContractError("备份内容缺失: " + str(source))
                if tree_sha256(source) != record.get("sha256"):
                    raise RuntimeContractError("备份内容完整性校验失败: " + str(source))
        except (KeyError, RuntimeContractError) as exc:
            die(str(exc))
    if args.dry_run:
        for record in manifest["records"]:
            print("restore" if record["existed"] else "remove", record["target"])
        return
    for record in reversed(manifest["records"]):
        target = lexical(Path(record["target"]))
        source = (backup_root / record["backup_relative"]).resolve()
        if target.exists() or target.is_symlink():
            remove_path(target)
        if record["existed"]:
            if record["kind"] == "directory":
                copy_tree_atomic(source, target)
            else:
                copy_file_atomic(source, target)
    print("[OK] 已恢复备份")


def add_component_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--component", choices=["all", "skills", "global", "agents"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-replace-global", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    add_component_options(install)
    install.set_defaults(func=command_install)
    uninstall = sub.add_parser("uninstall")
    add_component_options(uninstall)
    uninstall.set_defaults(func=command_uninstall)
    verify = sub.add_parser("verify")
    verify.set_defaults(func=command_verify)
    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=command_doctor)
    restore = sub.add_parser("restore")
    restore.add_argument("--backup")
    restore.add_argument("--dry-run", action="store_true")
    restore.set_defaults(func=command_restore)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
