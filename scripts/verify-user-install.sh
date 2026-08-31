#!/usr/bin/env bash
set -euo pipefail

codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
agents_home="$codex_home/agents"
expected_skills=(
  java-backend-engineering python-backend-ai-engineering vue-frontend-engineering
  data-middleware-ai-infrastructure log-observability-analysis engineering-quality-delivery
  multi-agent-independent-review technical-document-writing long-running-task-memory
)
expected_agents=(
  cp-review-functional-business.toml cp-review-compatibility-regression.toml
  cp-review-security-access.toml cp-review-performance-resources.toml
  cp-review-data-contract.toml cp-review-state-concurrency.toml
  cp-review-test-delivery.toml
)
doc_templates=(
  TECHNICAL_SOLUTION.template.md ARCHITECTURE_DESIGN.template.md IMPLEMENTATION_PLAN.template.md
  API_DESIGN.template.md DATABASE_DESIGN.template.md DEPLOYMENT_RUNBOOK.template.md
  INCIDENT_REPORT.template.md CODE_REVIEW_REPORT.template.md PROJECT_PROGRESS_REPORT.template.md
  TECHNICAL_SELECTION.template.md README.template.md MANAGEMENT_REPORT.template.md
)
memory_templates=(
  PROJECT_CONTEXT.template.md CURRENT_TASK.template.md PLAN.template.md PROGRESS.template.md
  DECISIONS.template.md HANDOFF.template.md KNOWN_ISSUES.template.md DELIVERY_RECORD.template.md
  CHECKPOINT_ENTRY.template.md RECOVERY_CHECKLIST.template.md
)
review_templates=(PRE_IMPLEMENTATION_REVIEW.template.md REVIEW_PLAN.template.md REVIEW_RESULT.template.md REVIEW_LEDGER.template.md)
log_templates=(LOG_ANALYSIS_REPORT.template.md LOG_TIMELINE.template.md LOG_EVIDENCE_LEDGER.template.md METRICS_ANALYSIS.template.md TRACE_ANALYSIS.template.md OBSERVABILITY_CORRELATION.template.md)
failed=0
agents_file="$codex_home/AGENTS.md"

if [[ -f "$agents_file" ]] &&
   grep -qF '<!-- codex-cross-project-assistant:begin -->' "$agents_file" &&
   grep -qF '<!-- codex-cross-project-assistant:end -->' "$agents_file"; then
  echo "[OK] 全局 AGENTS.md 受管区块: $agents_file"
else
  echo "[缺失或格式错误] 全局 AGENTS.md 受管区块: $agents_file"
  failed=1
fi

for name in "${expected_skills[@]}"; do
  dir="$skills_home/$name"
  if [[ ! -f "$dir/SKILL.md" ]]; then
    echo "[缺失] $dir/SKILL.md"; failed=1; continue
  fi
  if ! grep -Eq "^name:[[:space:]]+$name[[:space:]]*$" "$dir/SKILL.md" || ! grep -Eq '^description:' "$dir/SKILL.md"; then
    echo "[格式错误] $dir/SKILL.md"; failed=1
  elif [[ ! -f "$dir/agents/openai.yaml" ]]; then
    echo "[缺失] $dir/agents/openai.yaml"; failed=1
  else
    echo "[OK] Skill: $name"
  fi
done

for file in "${expected_agents[@]}"; do
  path="$agents_home/$file"
  if [[ ! -f "$path" ]]; then echo "[缺失] Reviewer: $path"; failed=1; continue; fi
  if ! grep -Eq '^name[[:space:]]*=' "$path" || ! grep -Eq '^description[[:space:]]*=' "$path" ||
     ! grep -Eq '^developer_instructions[[:space:]]*=' "$path" || ! grep -Eq '^sandbox_mode[[:space:]]*=[[:space:]]*"read-only"' "$path"; then
    echo "[格式错误] Reviewer: $path"; failed=1
  else
    echo "[OK] Reviewer: $file"
  fi
done

check_templates() {
  local dir="$1"; shift
  local file
  for file in "$@"; do
    [[ -f "$dir/$file" ]] || { echo "[缺失] 模板: $dir/$file"; failed=1; }
  done
}
check_templates "$skills_home/technical-document-writing/assets/templates" "${doc_templates[@]}"
check_templates "$skills_home/long-running-task-memory/assets/templates" "${memory_templates[@]}"
check_templates "$skills_home/multi-agent-independent-review/assets/templates" "${review_templates[@]}"
check_templates "$skills_home/log-observability-analysis/assets/templates" "${log_templates[@]}"

checkpoint="$skills_home/long-running-task-memory/scripts/checkpoint.py"
if [[ -f "$checkpoint" ]]; then echo "[OK] 持续检查点辅助脚本"; else echo "[缺失] $checkpoint"; failed=1; fi
review_controller="$skills_home/multi-agent-independent-review/scripts/review_controller.py"
if [[ -f "$review_controller" ]]; then echo "[OK] 复审状态控制器"; else echo "[缺失] $review_controller"; failed=1; fi

if [[ "$failed" -ne 0 ]]; then echo "验证失败。" >&2; exit 1; fi

echo "[OK] Skills: ${#expected_skills[@]} 个"
echo "[OK] 只读 Reviewer: ${#expected_agents[@]} 个"
echo "[OK] 模板: 文档 ${#doc_templates[@]} / 记忆 ${#memory_templates[@]} / 复审 ${#review_templates[@]} / 日志 ${#log_templates[@]}"
echo "验证通过。请在 Codex 中运行 /skills；新增内容未刷新时重启 Codex。"
