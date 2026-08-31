#!/usr/bin/env python3
"""Validate the local Codex Skills package with only Python standard library."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TEMPLATES = {
    "TECHNICAL_SOLUTION.template.md",
    "ARCHITECTURE_DESIGN.template.md",
    "IMPLEMENTATION_PLAN.template.md",
    "API_DESIGN.template.md",
    "DATABASE_DESIGN.template.md",
    "DEPLOYMENT_RUNBOOK.template.md",
    "INCIDENT_REPORT.template.md",
    "CODE_REVIEW_REPORT.template.md",
    "PROJECT_PROGRESS_REPORT.template.md",
    "TECHNICAL_SELECTION.template.md",
    "README.template.md",
    "MANAGEMENT_REPORT.template.md",
}


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"缺少文件: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def validate_markdown_fences(path: Path, text: str) -> None:
    if len(re.findall(r"^```", text, flags=re.MULTILINE)) % 2:
        fail(f"Markdown 代码块未闭合: {path.relative_to(ROOT)}")


def parse_frontmatter(path: Path, text: str) -> tuple[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    if not match:
        fail(f"SKILL.md 缺少 YAML Frontmatter: {path.relative_to(ROOT)}")
    meta = match.group(1)
    name_match = re.search(r"(?m)^name:\s*([^\n]+?)\s*$", meta)
    desc_match = re.search(r"(?m)^description:\s*(?:>-\s*\n)?(.+)", meta, flags=re.DOTALL)
    if not name_match or not desc_match:
        fail(f"SKILL.md 缺少 name 或 description: {path.relative_to(ROOT)}")
    name = name_match.group(1).strip().strip('"\'')
    description = " ".join(line.strip() for line in desc_match.group(1).splitlines()).strip()
    if not description:
        fail(f"Skill description 为空: {path.relative_to(ROOT)}")
    return name, description


def main() -> None:
    manifest = json.loads(read(ROOT / "manifest.json"))
    if manifest.get("version") != "2.0.0":
        fail("manifest.json 版本不是 2.0.0")
    skills = manifest.get("skills")
    if not isinstance(skills, list) or not skills:
        fail("manifest.json 没有有效 skills 列表")

    agents = read(ROOT / "global" / "AGENTS.md")
    if agents.count("<!-- codex-cross-project-assistant:begin -->") != 1 or agents.count(
        "<!-- codex-cross-project-assistant:end -->"
    ) != 1:
        fail("全局 AGENTS.md 受管标记必须各出现一次")
    if len(agents.encode("utf-8")) > 24 * 1024:
        fail("全局 AGENTS.md 超过 24 KiB，可能挤占项目级指令空间")
    validate_markdown_fences(ROOT / "global" / "AGENTS.md", agents)
    ok(f"全局 AGENTS.md: {len(agents.encode('utf-8'))} bytes")

    manifest_names = []
    for item in skills:
        expected_name = item.get("name")
        if not expected_name:
            fail("manifest skill 缺少 name")
        manifest_names.append(expected_name)
        skill_dir = ROOT / "skills" / expected_name
        skill_file = skill_dir / "SKILL.md"
        text = read(skill_file)
        name, description = parse_frontmatter(skill_file, text)
        if name != expected_name:
            fail(f"Skill 目录名与 name 不一致: {expected_name} != {name}")
        if len(description) > 500:
            fail(f"Skill description 过长: {expected_name}")
        validate_markdown_fences(skill_file, text)
        read(skill_dir / "agents" / "openai.yaml")

        for relative in re.findall(r"`((?:references|assets)/[^`]+)`", text):
            if not (skill_dir / relative).exists():
                fail(f"Skill 引用不存在: {expected_name}/{relative}")
        ok(f"Skill: {expected_name}")

    actual_names = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
    if sorted(manifest_names) != actual_names:
        fail(f"manifest 与实际 Skills 不一致: manifest={sorted(manifest_names)}, actual={actual_names}")

    doc_templates_dir = ROOT / "skills" / "technical-document-writing" / "assets" / "templates"
    actual_templates = {p.name for p in doc_templates_dir.glob("*.md")}
    missing = EXPECTED_TEMPLATES - actual_templates
    if missing:
        fail(f"缺少技术文档模板: {sorted(missing)}")
    ok(f"技术文档模板: {len(actual_templates)} 个")

    for path in ROOT.rglob("*.md"):
        text = read(path)
        validate_markdown_fences(path, text)
    ok("所有 Markdown 代码块闭合")

    required_scripts = {
        "install-user.ps1", "install-user.sh", "verify-user-install.ps1", "verify-user-install.sh",
        "uninstall-user.ps1", "uninstall-user.sh", "install-repo-skills.ps1", "install-repo-skills.sh",
        "uninstall-repo-skills.ps1", "uninstall-repo-skills.sh",
    }
    actual_scripts = {p.name for p in (ROOT / "scripts").iterdir() if p.is_file()}
    missing_scripts = required_scripts - actual_scripts
    if missing_scripts:
        fail(f"缺少脚本: {sorted(missing_scripts)}")
    ok("安装、验证和卸载脚本齐全")

    print("验证通过。")


if __name__ == "__main__":
    main()
