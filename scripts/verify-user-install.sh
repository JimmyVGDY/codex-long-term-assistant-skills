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
  long-running-task-memory
)
failed=0

if [[ -f "$codex_home/AGENTS.md" ]]; then
  echo "[OK] 全局 AGENTS.md: $codex_home/AGENTS.md"
else
  echo "[缺失] $codex_home/AGENTS.md"
  failed=1
fi

for name in "${expected[@]}"; do
  file="$skills_home/$name/SKILL.md"
  if [[ ! -f "$file" ]]; then
    echo "[缺失] $file"
    failed=1
    continue
  fi
  if grep -Eq "^name:[[:space:]]+$name[[:space:]]*$" "$file" && grep -Eq '^description:' "$file"; then
    echo "[OK] Skill: $name"
  else
    echo "[格式错误] $file"
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  echo "验证失败。" >&2
  exit 1
fi

echo "验证通过。请在 Codex 中运行 /skills；未刷新时重启 Codex。"
