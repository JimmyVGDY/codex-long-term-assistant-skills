#!/usr/bin/env bash
set -euo pipefail

codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
expected=(
  java-backend-engineering
  python-backend-ai-engineering
  vue-frontend-engineering
  data-middleware-ai-infrastructure
  engineering-quality-delivery
  technical-document-writing
  long-running-task-memory
)
templates=(
  TECHNICAL_SOLUTION.template.md
  ARCHITECTURE_DESIGN.template.md
  IMPLEMENTATION_PLAN.template.md
  API_DESIGN.template.md
  DATABASE_DESIGN.template.md
  DEPLOYMENT_RUNBOOK.template.md
  INCIDENT_REPORT.template.md
  CODE_REVIEW_REPORT.template.md
  PROJECT_PROGRESS_REPORT.template.md
  TECHNICAL_SELECTION.template.md
  README.template.md
  MANAGEMENT_REPORT.template.md
)
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

for name in "${expected[@]}"; do
  dir="$skills_home/$name"
  file="$dir/SKILL.md"
  openai="$dir/agents/openai.yaml"
  if [[ ! -f "$file" ]]; then
    echo "[缺失] $file"
    failed=1
    continue
  fi
  if ! grep -Eq "^name:[[:space:]]+$name[[:space:]]*$" "$file" || ! grep -Eq '^description:' "$file"; then
    echo "[格式错误] $file"
    failed=1
  elif [[ ! -f "$openai" ]]; then
    echo "[缺失] $openai"
    failed=1
  else
    echo "[OK] Skill: $name"
  fi
done

template_dir="$skills_home/technical-document-writing/assets/templates"
for template in "${templates[@]}"; do
  if [[ ! -f "$template_dir/$template" ]]; then
    echo "[缺失] 文档模板: $template_dir/$template"
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  echo "验证失败。" >&2
  exit 1
fi

echo "[OK] 技术文档模板: ${#templates[@]} 个"
echo "验证通过。请在 Codex 中运行 /skills；未刷新时重启 Codex。"
