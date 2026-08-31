#!/usr/bin/env python3
"""Semantic consistency checks for the Codex V4.2 package."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "codex"
VERSION = "4.2.0"
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)
    print("[FAIL]", message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


manifest = json.loads(read(ROOT / "manifest.json"))
if manifest.get("version") != VERSION:
    fail("manifest 版本不一致")
skills = {item["name"] for item in manifest["skills"]}

for skill_file in ROOT.glob("skills/*/SKILL.md"):
    text = read(skill_file)
    match = re.search(r"(?m)^name:\s*([^\n]+)", text)
    if not match or match.group(1).strip() not in skills:
        fail("Skill 名称不一致 " + str(skill_file.relative_to(ROOT)))
    for reference in re.findall(r"\$([a-z][a-z0-9-]+)", text):
        if reference not in skills:
            fail("未知 Skill 引用 {} in {}".format(reference, skill_file.relative_to(ROOT)))
    if skill_file.parent.name != "multi-agent-independent-review" and "## 模型与委派成本" not in text:
        fail("Skill 缺少模型与委派成本规则 " + str(skill_file.relative_to(ROOT)))
    if skill_file.parent.name == "multi-agent-independent-review" and "terra-high" not in text:
        fail("复审 Skill 缺少四级模型上限")

allowed_old_name_files = {
    "FRONTEND_SKILL_MIGRATION.md",
    "CHANGELOG.md",
    "VALIDATION_REPORT.md",
    "README.md",
    "FRONTEND_SKILL_V4_DESIGN.md",
}
historical_v32_files = {
    "P0_OPTIMIZATION_DESIGN.md",
    "V3_DESIGN_OVERVIEW.md",
    "V3_1_LOG_ANALYSIS_DESIGN.md",
    "CHANGELOG.md",
}
for markdown in ROOT.rglob("*.md"):
    text = read(markdown)
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
    if len(read(index_file).splitlines()) > 120:
        fail("Reference 未分片 " + str(index_file.relative_to(ROOT)))
for reference in ROOT.glob("skills/*/references/*.md"):
    lines = read(reference).splitlines()
    if len(lines) > 120 and "## 本文件目录" not in lines[:30]:
        fail("长 Reference 缺少前置目录 " + str(reference.relative_to(ROOT)))

config = read(ROOT / "config/agents.example.toml")
if len(re.findall(r"(?m)^\s*\[agents\]\s*$", config)) != 1:
    fail("agents.example.toml 必须只有一个 [agents] 表")
for expected in [
    'max_concurrent_threads_per_session = 3',
    'default_subagent_model = "gpt-5.6-luna"',
    'default_subagent_reasoning_effort = "medium"',
]:
    if expected not in config:
        fail("缺少推荐 Codex 配置: " + expected)

for agent_file in ROOT.glob("custom-agents/*.toml"):
    text = read(agent_file)
    if re.search(r"(?m)^\s*model\s*=", text):
        fail("Reviewer TOML 不应写死 model: " + agent_file.name)
    if re.search(r"(?m)^\s*model_reasoning_effort\s*=", text):
        fail("Reviewer TOML 不应写死 model_reasoning_effort: " + agent_file.name)
    if "按渐进式顺序读取" not in text or "默认最多返回 8 个根因组" not in text:
        fail("Reviewer 缺少渐进读取或输出收敛规则: " + agent_file.name)

global_text = read(ROOT / "global/AGENTS.md")
if len(global_text.splitlines()) > 220:
    fail("全局 AGENTS.md 超过 220 行，可能重新膨胀")
for expected in ["luna-low", "luna-medium", "terra-medium", "terra-high", "累计最多 6"]:
    if expected not in global_text:
        fail("全局规则缺少 V4.2 策略: " + expected)

execution_guard = read(ROOT / "skills/engineering-quality-delivery/scripts/execution_guard.py")
review_packet = read(ROOT / "skills/multi-agent-independent-review/scripts/review_packet.py")
review_controller = read(ROOT / "skills/multi-agent-independent-review/scripts/review_controller.py")
checkpoint = read(ROOT / "skills/long-running-task-memory/scripts/checkpoint.py")
if "untracked_sha256" not in execution_guard:
    fail("执行证据指纹未覆盖 untracked 内容")
for expected in ["packet-summary.md", "diff-stat.txt", "name-status.txt", "command_freshness"]:
    if expected not in review_packet:
        fail("审查包缺少 V4.2 能力: " + expected)
for expected in [
    '"luna-low"',
    '"luna-medium"',
    '"terra-medium"',
    '"terra-high"',
    '"max_parallel_reviewers": 3',
    '"max_total_reviewers": 6',
    '"max_terra_high_reviewers": 1',
    "find_previous_same_dispatch",
]:
    if expected not in review_controller:
        fail("复审控制器缺少 V4.2 策略: " + expected)
write_success = review_controller.find('probe_result == "write-succeeded"')
parent_readonly = review_controller.find('parent_sandbox == "read-only"')
if write_success < 0 or parent_readonly < 0 or write_success > parent_readonly:
    fail("隔离判定没有优先处理写入成功反证")
for expected in ["DEFAULT_HOT_LIMIT = 20", 'default=3', "--force-append", "checkpoint_payload_fingerprint"]:
    if expected not in checkpoint:
        fail("检查点工具缺少 V4.2 能力: " + expected)

if ERRORS:
    print("语义校验失败", len(ERRORS))
    raise SystemExit(1)
print("V4.2 语义校验通过。")
