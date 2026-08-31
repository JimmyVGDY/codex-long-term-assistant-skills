#!/usr/bin/env python3
"""V4.2 install/verify/doctor/uninstall/restore manager (codex)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = 'codex'
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
SKILLS = [item["name"] for item in MANIFEST["skills"]]
DEPRECATED = MANIFEST.get("deprecated_skills", [])
BEGIN = '<!-- codex-cross-project-assistant:begin -->'
END = '<!-- codex-cross-project-assistant:end -->'
LEGACY_BEGIN = '<!-- codex-cross-project-assistant:begin -->'
LEGACY_END = '<!-- codex-cross-project-assistant:end -->'


def home_paths() -> Tuple[Path, Path, Path, Path, Optional[Path], Path]:
    home = Path.home()
    app = Path(os.environ.get("CODEX_HOME") or (home / ".codex")).expanduser().resolve()
    skills = app / "skills"
    agents = app / "agents"
    global_file = app / "AGENTS.md"
    legacy = home / ".agents" / "skills"
    backups = home / ".codex-skill-backups"
    return app, skills, agents, global_file, legacy, backups


def source_agents_dir() -> Path:
    return ROOT / "custom-agents"


def planned_operations(component: str) -> List[Tuple[str, str]]:
    _app, skills, agents, global_file, legacy, _backups = home_paths()
    operations: List[Tuple[str, str]] = []
    if component in {"all", "global"}:
        operations.append(("merge-global", str(global_file)))
    if component in {"all", "skills"}:
        for name in DEPRECATED:
            operations.append(("remove-deprecated", str(skills / name)))
        for name in SKILLS:
            operations.append(("replace-skill", str(skills / name)))
        if legacy is not None:
            for name in SKILLS + DEPRECATED:
                if (legacy / name).exists():
                    operations.append(("remove-legacy-duplicate", str(legacy / name)))
    if component in {"all", "agents"}:
        for item in source_agents_dir().iterdir():
            if item.is_file() and item.name.lower() != "readme.md":
                operations.append(("replace-agent", str(agents / item.name)))
    return operations


def backup_path(source: Path, backup_root: Path, relative: str, records: List[Dict[str, Any]]) -> None:
    target = backup_root / relative
    records.append({"target": str(source), "backup": str(target), "existed": source.exists()})
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def merge_global(target: Path, source: Path, force: bool = False) -> None:
    managed = source.read_text(encoding="utf-8-sig").strip()
    target.parent.mkdir(parents=True, exist_ok=True)
    if force or not target.exists():
        target.write_text(managed + "\n", encoding="utf-8")
        return

    existing = target.read_text(encoding="utf-8-sig")
    if LEGACY_BEGIN != BEGIN:
        existing = existing.replace(LEGACY_BEGIN, BEGIN).replace(LEGACY_END, END)
    begin_count = existing.count(BEGIN)
    end_count = existing.count(END)
    if begin_count != end_count or begin_count > 1:
        raise RuntimeError("全局受管标记异常")
    if begin_count == 0:
        result = existing.rstrip() + "\n\n" + managed + "\n"
    else:
        result = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), managed, existing, count=1, flags=re.S)
    target.write_text(result, encoding="utf-8")


def command_install(args: argparse.Namespace) -> None:
    app, skills, agents, global_file, legacy, backups = home_paths()
    for operation, path in planned_operations(args.component):
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
    backup_root.mkdir(parents=True, exist_ok=True)

    if args.component in {"all", "global"}:
        backup_path(global_file, backup_root, "global/" + global_file.name, records)
        merge_global(global_file, ROOT / "global" / global_file.name, args.force_replace_global)

    if args.component in {"all", "skills"}:
        skills.mkdir(parents=True, exist_ok=True)
        for name in DEPRECATED:
            target = skills / name
            backup_path(target, backup_root, "deprecated-skills/" + name, records)
            if target.exists():
                shutil.rmtree(target)
        if legacy is not None:
            for name in SKILLS + DEPRECATED:
                target = legacy / name
                if target.exists():
                    backup_path(target, backup_root, "legacy-skills/" + name, records)
                    shutil.rmtree(target)
        for name in SKILLS:
            target = skills / name
            backup_path(target, backup_root, "skills/" + name, records)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(ROOT / "skills" / name, target)

    if args.component in {"all", "agents"}:
        agents.mkdir(parents=True, exist_ok=True)
        for item in source_agents_dir().iterdir():
            if not item.is_file() or item.name.lower() == "readme.md":
                continue
            target = agents / item.name
            backup_path(target, backup_root, "agents/" + item.name, records)
            shutil.copy2(item, target)

    backup_manifest = {
        "platform": PLATFORM,
        "version": MANIFEST["version"],
        "created_at": timestamp,
        "records": records,
    }
    (backup_root / "backup-manifest.json").write_text(
        json.dumps(backup_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    install_state = {
        "version": MANIFEST["version"],
        "release_name": MANIFEST["release_name"],
        "installed_at": timestamp,
        "skills_home": str(skills),
        "backup": str(backup_root),
    }
    (app / ".cross-project-assistant-install.json").write_text(
        json.dumps(install_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("[OK] 安装完成，备份:", backup_root)


def collect_verification_errors() -> List[str]:
    _app, skills, agents, global_file, legacy, _backups = home_paths()
    errors: List[str] = []
    if not global_file.is_file():
        errors.append("缺少全局文件")
    else:
        text = global_file.read_text(encoding="utf-8-sig")
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            errors.append("受管标记不是一份")
    for name in SKILLS:
        if not (skills / name / "SKILL.md").is_file():
            errors.append("缺少 Skill " + name)
    for name in DEPRECATED:
        if (skills / name).exists():
            errors.append("残留废弃 Skill " + name)
    if legacy is not None:
        for name in SKILLS + DEPRECATED:
            if (legacy / name).exists():
                errors.append("旧路径存在同名 Skill " + str(legacy / name))
    for item in source_agents_dir().iterdir():
        if item.is_file() and item.name.lower() != "readme.md" and not (agents / item.name).is_file():
            errors.append("缺少 Agent " + item.name)
    return errors


def command_verify(_args: argparse.Namespace) -> None:
    errors = collect_verification_errors()
    if errors:
        for item in errors:
            print("[FAIL]", item)
        raise SystemExit(1)
    print("[OK] 用户级安装验证通过")


def command_doctor(_args: argparse.Namespace) -> None:
    app, skills, agents, global_file, legacy, backups = home_paths()
    print("# Doctor")
    print("platform:", PLATFORM)
    print("app_home:", app)
    print("skills_home:", skills)
    print("agents_home:", agents)
    print("global:", global_file)
    print("version:", MANIFEST["version"])
    print("global_exists:", global_file.exists())
    print("skills_found:", sum((skills / name / "SKILL.md").is_file() for name in SKILLS), "/", len(SKILLS))
    print("deprecated_present:", [name for name in DEPRECATED if (skills / name).exists()])
    print("legacy_duplicates:", [name for name in SKILLS if legacy is not None and (legacy / name).exists()])
    print("python:", sys.executable)
    print("git:", shutil.which("git") or "missing")
    print("backups:", backups)
    print("verification_errors:", collect_verification_errors())


def remove_managed_global(global_file: Path) -> None:
    if not global_file.exists():
        return
    text = global_file.read_text(encoding="utf-8-sig")
    text = text.replace(LEGACY_BEGIN, BEGIN).replace(LEGACY_END, END)
    text = re.sub(r"\n?" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "\n", text, flags=re.S)
    global_file.write_text(text.strip() + "\n" if text.strip() else "", encoding="utf-8")


def command_uninstall(args: argparse.Namespace) -> None:
    _app, skills, agents, global_file, _legacy, _backups = home_paths()
    if args.dry_run:
        for _operation, path in planned_operations(args.component):
            print("remove/restore-managed:", path)
        print("[DRY-RUN] 未修改文件")
        return
    if args.component in {"all", "global"}:
        remove_managed_global(global_file)
    if args.component in {"all", "skills"}:
        for name in SKILLS + DEPRECATED:
            target = skills / name
            if target.exists():
                shutil.rmtree(target)
    if args.component in {"all", "agents"}:
        for item in source_agents_dir().iterdir():
            target = agents / item.name
            if item.is_file() and item.name.lower() != "readme.md" and target.exists():
                target.unlink()
    print("[OK] 已卸载本包受管资源")


def command_restore(args: argparse.Namespace) -> None:
    _app, _skills, _agents, _global_file, _legacy, backups = home_paths()
    candidates = sorted(path for path in backups.glob("*") if (path / "backup-manifest.json").is_file())
    if not candidates:
        raise SystemExit("没有可恢复备份")
    backup_root = Path(args.backup).expanduser().resolve() if args.backup else candidates[-1]
    manifest = json.loads((backup_root / "backup-manifest.json").read_text(encoding="utf-8"))
    print("restore from", backup_root)
    if args.dry_run:
        for record in manifest["records"]:
            print("restore" if record["existed"] else "remove", record["target"])
        return
    for record in reversed(manifest["records"]):
        target = Path(record["target"])
        source = Path(record["backup"])
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if record["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
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
