#!/usr/bin/env python3
"""Semantic consistency checks for the Codex V5.1 package."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
VERSION = "5.1.0"
ERRORS: List[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)
    print("[FAIL]", message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


manifest = json.loads(read(ROOT / "manifest.json"))
if manifest.get("version") != VERSION:
    fail("manifest 版本不一致")
skills = {item["name"] for item in manifest.get("skills", [])}

controlled = manifest.get("controlled_evolution") or {}
if controlled.get("runtime") != "runtime/cp_runtime/evolution":
    fail("manifest 未声明唯一 Evolution Runtime")
if controlled.get("execution_authorization") != "NONE" or controlled.get("automatic_execution") is not False:
    fail("受控自进化执行边界不正确")
if controlled.get("implementation_requires_new_task") is not True:
    fail("受控自进化未要求独立实施任务")

skill_files = list(ROOT.glob("skills/*/SKILL.md"))
if len(skill_files) != len(skills):
    fail("SKILL.md 数量与 manifest 不一致")
for skill_file in skill_files:
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
    "FRONTEND_SKILL_MIGRATION.md", "CHANGELOG.md", "VALIDATION_REPORT.md",
    "README.md", "FRONTEND_SKILL_V4_DESIGN.md",
}
historical_v32_files = {
    "P0_OPTIMIZATION_DESIGN.md", "V3_DESIGN_OVERVIEW.md",
    "V3_1_LOG_ANALYSIS_DESIGN.md", "CHANGELOG.md",
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
project_governance = manifest.get("project_governance") or {}
if project_governance.get("runtime") != "runtime/cp_runtime":
    fail("manifest 未声明唯一 cp_runtime")
if project_governance.get("project_binding_fail_closed") is not True:
    fail("项目绑定未声明失败关闭")

runtime_dirs = [path for path in ROOT.rglob("cp_runtime") if path.is_dir()]
if len(runtime_dirs) != 1 or runtime_dirs[0] != ROOT / "runtime" / "cp_runtime":
    fail("cp_runtime 权威实现不是唯一一份")

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
if len(global_text.splitlines()) > 240:
    fail("全局 AGENTS.md 超过 240 行，可能重新膨胀")
for expected in [
    "luna-low", "luna-medium", "terra-medium", "terra-high", "累计最多 6",
    "Project Profile", "Approval", "Evidence", "Finalization",
    "V5.1 受控自进化", "execution_authorization", "不得自动修改",
]:
    if expected not in global_text:
        fail("全局规则缺少继承策略: " + expected)

execution_guard = read(ROOT / "skills/engineering-quality-delivery/scripts/execution_guard.py")
review_packet = read(ROOT / "skills/multi-agent-independent-review/scripts/review_packet.py")
review_controller = read(ROOT / "skills/multi-agent-independent-review/scripts/review_controller.py")
checkpoint = read(ROOT / "skills/long-running-task-memory/scripts/checkpoint.py")
for expected in ["Task Envelope V2", "authorize-action", "record-action", "finalize", "project_profile"]:
    if expected not in execution_guard:
        fail("执行守卫缺少继承能力: " + expected)
if "untracked_sha256" not in execution_guard:
    fail("执行证据指纹未覆盖 untracked 内容")
for expected in ["packet-summary.md", "diff-stat.txt", "name-status.txt", "command_freshness"]:
    if expected not in review_packet:
        fail("审查包缺少继承能力: " + expected)
for expected in [
    '"luna-low"', '"luna-medium"', '"terra-medium"', '"terra-high"',
    '"max_parallel_reviewers": 3', '"max_total_reviewers": 6',
    '"max_terra_high_reviewers": 1', "find_previous_same_dispatch",
]:
    if expected not in review_controller:
        fail("复审控制器缺少继承策略: " + expected)
write_success = review_controller.find('probe_result == "write-succeeded"')
parent_readonly = review_controller.find('parent_sandbox == "read-only"')
if write_success < 0 or parent_readonly < 0 or write_success > parent_readonly:
    fail("隔离判定没有优先处理写入成功反证")
for expected in ["DEFAULT_HOT_LIMIT = 20", 'default=3', "--force-append", "checkpoint_payload_fingerprint"]:
    if expected not in checkpoint:
        fail("检查点工具缺少继承能力: " + expected)

for relative in [
    "docs/V5_0_PROJECT_GOVERNANCE_AND_EVIDENCE_CLOSURE.md",
    "docs/V5.0_升级说明与迁移指南.md",
    "docs/V5.1_升级说明与迁移指南.md",
    "docs/PROJECT_CONTEXT_AND_ONBOARDING.md",
    "docs/APPROVAL_EVIDENCE_FINALIZATION.md",
    "docs/AUTHORITY_REGISTRY.md",
    "docs/evolution/SELF_EVOLUTION_ARCHITECTURE.md",
    "docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md",
    "RELEASE_NOTES_V5.1.md",
]:
    if not (ROOT / relative).is_file():
        fail("缺少版本文档 " + relative)
changelog = read(ROOT / "CHANGELOG.md")
if "## 5.0.0 - 2026-08-26" not in changelog:
    fail("CHANGELOG 缺少 V5.0 历史记录")
if "## 5.1.0 - 2026-08-26" not in changelog:
    fail("CHANGELOG 缺少 V5.1 发布记录")

controlled = manifest.get("controlled_evolution") or {}
if controlled.get("runtime") != "runtime/cp_runtime/evolution":
    fail("manifest 未声明唯一 Evolution Runtime")
if controlled.get("execution_authorization") != "NONE":
    fail("Evolution 提案执行授权必须固定为 NONE")
if controlled.get("automatic_execution") is not False or controlled.get("automatic_acceptance") is not False:
    fail("Evolution 不得自动执行或自动接受")
evolution_dirs = [path for path in ROOT.rglob("evolution") if path.is_dir() and path.parent.name == "cp_runtime"]
if evolution_dirs != [ROOT / "runtime" / "cp_runtime" / "evolution"]:
    fail("Evolution Runtime 权威实现不是唯一一份")
for relative in [
    "runtime/cp_runtime/evolution/contracts.py",
    "runtime/cp_runtime/evolution/observation.py",
    "runtime/cp_runtime/evolution/analysis.py",
    "runtime/cp_runtime/evolution/proposal.py",
    "runtime/cp_runtime/evolution/registry.py",
    "runtime/cp_runtime/evolution/service.py",
    "runtime/cp_runtime/evolution/cli.py",
    "runtime/cp_runtime/evolution/manifest.json",
    "config/evolution-policy.json",
    "scripts/evolution.py",
    "scripts/validate-v51-evolution.py",
    "tests/test_v51_controlled_evolution.py",
]:
    if not (ROOT / relative).is_file():
        fail("缺少 V5.1 受控自进化资源 " + relative)
if "## 5.1.0 - 2026-08-26" not in read(ROOT / "CHANGELOG.md"):
    fail("CHANGELOG 缺少 V5.1 发布记录")

package_manager = read(ROOT / "scripts/package_manager.py")
for expected in ["EVOLUTION_TOOL_SOURCE", '"tools/evolution.py"', "evolution_tool_target"]:
    if expected not in package_manager:
        fail("安装器缺少 V5.1 Evolution Tool 管理: " + expected)
for relative in [
    "docs/V5.1_升级说明与迁移指南.md",
    "docs/evolution/SELF_EVOLUTION_ARCHITECTURE.md",
    "docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md",
    "runtime/cp_runtime/evolution/manifest.json",
    "config/evolution-policy.json",
]:
    if not (ROOT / relative).is_file():
        fail("缺少 V5.1 资源 " + relative)

if ERRORS:
    print("语义校验失败", len(ERRORS))
    raise SystemExit(1)
print("V5.1 语义校验通过。")
