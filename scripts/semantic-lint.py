#!/usr/bin/env python3
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = 'codex'
VERSION = "4.1.0"
INVOCATION = '$'
errors = []


def fail(message):
    errors.append(message)
    print("[FAIL]", message)


def read_text(path):
    return path.read_text(encoding="utf-8-sig")


manifest = json.loads(read_text(ROOT / "manifest.json"))
if manifest.get("version") != VERSION:
    fail("manifest 版本不一致")
skills = {item["name"] for item in manifest["skills"]}
for skill_file in ROOT.glob("skills/*/SKILL.md"):
    text = read_text(skill_file)
    match = re.search(r"(?m)^name:\s*([^\n]+)", text)
    if not match or match.group(1).strip() not in skills:
        fail("Skill 名称不一致 " + str(skill_file))
    pattern = re.escape(INVOCATION) + r"([a-z][a-z0-9-]+)"
    for reference in re.findall(pattern, text):
        if reference not in skills:
            fail("未知 Skill 引用 " + reference + " in " + str(skill_file.relative_to(ROOT)))

allowed_old_name_files = {
    "FRONTEND_SKILL_MIGRATION.md",
    "CHANGELOG.md",
    "VALIDATION_REPORT.md",
    "README.md",
    "FRONTEND_SKILL_V4_DESIGN.md",
    "FRONTEND_SKILL_MIGRATION.md",
}
historical_v32_files = {
    "P0_OPTIMIZATION_DESIGN.md", "V3_DESIGN_OVERVIEW.md",
    "V3_1_LOG_ANALYSIS_DESIGN.md", "CHANGELOG.md",
}
for markdown in ROOT.rglob("*.md"):
    text = read_text(markdown)
    if "vue-frontend-engineering" in text and markdown.name not in allowed_old_name_files:
        fail("非迁移文档残留旧 Skill " + str(markdown.relative_to(ROOT)))
    if "Java、Python、Vue" in text:
        fail("残留 Vue 专用领域表述 " + str(markdown.relative_to(ROOT)))
    if "v3.2" in text and markdown.name not in historical_v32_files:
        fail("当前文档残留 v3.2 语义 " + str(markdown.relative_to(ROOT)))
    if '.py""' in text:
        fail("脚本路径存在重复引号 " + str(markdown.relative_to(ROOT)))
    if len(re.findall(r"^```", text, re.M)) % 2:
        fail("代码块未闭合 " + str(markdown.relative_to(ROOT)))

if manifest.get("user_skills_target") != "${CODEX_HOME:-$HOME/.codex}/skills":
    fail("Codex Skill 目标路径不正确")

for index_file in ROOT.glob("skills/*/references/*rules.md"):
    if sum(1 for _line in index_file.open(encoding="utf-8")) > 120:
        fail("Reference 未分片 " + str(index_file.relative_to(ROOT)))
for reference in ROOT.glob("skills/*/references/*.md"):
    lines = read_text(reference).splitlines()
    if len(lines) > 120 and "## 本文件目录" not in lines[:30]:
        fail("长 Reference 缺少前置目录 " + str(reference.relative_to(ROOT)))

execution_guard = read_text(ROOT / "skills" / "engineering-quality-delivery" / "scripts" / "execution_guard.py")
review_packet = read_text(ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_packet.py")
if "untracked_sha256" not in execution_guard:
    fail("执行证据指纹未覆盖 untracked 内容")
if "collect_untracked" not in review_packet or "validate-result" not in review_packet:
    fail("审查包未覆盖 untracked 快照或结构化结果验证")
review_controller = read_text(ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_controller.py")
write_success_index = review_controller.find('probe_result == "write-succeeded"')
parent_readonly_index = review_controller.find('parent_sandbox == "read-only"')
if write_success_index < 0 or parent_readonly_index < 0 or write_success_index > parent_readonly_index:
    fail("隔离判定没有优先处理写入成功反证")

if errors:
    print("语义校验失败", len(errors))
    raise SystemExit(1)
print("语义校验通过。")
