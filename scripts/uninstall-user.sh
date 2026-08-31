#!/usr/bin/env bash
set -euo pipefail

component="${1:-all}"
case "$component" in
  all|skills|global) ;;
  *) echo "用法: $0 [all|skills|global]" >&2; exit 2 ;;
esac

codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$HOME/.codex-skill-backups/uninstall-$timestamp"
begin_marker='<!-- codex-cross-project-assistant:begin -->'
end_marker='<!-- codex-cross-project-assistant:end -->'
managed=(
  java-backend-engineering
  python-backend-ai-engineering
  vue-frontend-engineering
  data-middleware-ai-infrastructure
  engineering-quality-delivery
  technical-document-writing
  long-running-task-memory
)

backup_path() {
  local src="$1" relative="$2"
  [[ -e "$src" ]] || return 0
  mkdir -p "$(dirname "$backup_root/$relative")"
  cp -a "$src" "$backup_root/$relative"
}

remove_global_block() {
  local target="$codex_home/AGENTS.md"
  [[ -f "$target" ]] || { echo "未找到全局 AGENTS.md，跳过。"; return; }
  backup_path "$target" "codex/AGENTS.md"
  local begin_count end_count
  begin_count="$(grep -cF "$begin_marker" "$target" || true)"
  end_count="$(grep -cF "$end_marker" "$target" || true)"
  if [[ "$begin_count" -ne "$end_count" || "$begin_count" -gt 1 ]]; then
    echo "AGENTS.md 的受管标记不完整或重复，已停止卸载: $target" >&2
    exit 1
  fi
  [[ "$begin_count" -eq 1 ]] || { echo "AGENTS.md 中没有本包受管区块，跳过。"; return; }

  local start end tmp total
  start="$(grep -nF "$begin_marker" "$target" | cut -d: -f1)"
  end="$(grep -nF "$end_marker" "$target" | cut -d: -f1)"
  tmp="$(mktemp)"
  if [[ "$start" -gt 1 ]]; then head -n $((start - 1)) "$target" >> "$tmp"; fi
  total="$(wc -l < "$target")"
  if [[ "$end" -lt "$total" ]]; then tail -n +$((end + 1)) "$target" >> "$tmp"; fi

  if grep -q '[^[:space:]]' "$tmp"; then
    awk 'BEGIN{blank=0} /^[[:space:]]*$/{blank++; if(blank<=2) print; next} {blank=0; print}' "$tmp" > "$target"
    echo "已移除本包受管区块，其他规则保持不变: $target"
  else
    rm -f "$target"
    echo "已删除仅包含本包规则的 AGENTS.md: $target"
  fi
  rm -f "$tmp"
}

remove_skills() {
  for name in "${managed[@]}"; do
    local target="$skills_home/$name"
    if [[ -d "$target" ]]; then
      backup_path "$target" "skills/$name"
      rm -rf "$target"
      echo "已卸载 Skill: $name"
    fi
  done
}

case "$component" in
  all) remove_global_block; remove_skills ;;
  skills) remove_skills ;;
  global) remove_global_block ;;
esac

echo "卸载完成。其他 Skills 和 AGENTS.md 中的非本包规则未被删除。"
echo "备份目录: $backup_root"
