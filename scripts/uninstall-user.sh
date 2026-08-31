#!/usr/bin/env bash
set -euo pipefail

component="${1:-all}"
[[ "$component" == "review-agents" ]] && component="agents"
case "$component" in all|skills|global|agents) ;; *) echo "用法: $0 [all|skills|global|agents]" >&2; exit 2 ;; esac

codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
agents_home="$codex_home/agents"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$HOME/.codex-skill-backups/uninstall-$timestamp"
begin_marker='<!-- codex-cross-project-assistant:begin -->'
end_marker='<!-- codex-cross-project-assistant:end -->'
managed_skills=(java-backend-engineering python-backend-ai-engineering vue-frontend-engineering data-middleware-ai-infrastructure log-observability-analysis engineering-quality-delivery multi-agent-independent-review technical-document-writing long-running-task-memory)
managed_agents=(cp-review-functional-business.toml cp-review-compatibility-regression.toml cp-review-security-access.toml cp-review-performance-resources.toml cp-review-data-contract.toml cp-review-state-concurrency.toml cp-review-test-delivery.toml)

backup_path() { local src="$1" relative="$2"; [[ -e "$src" ]] || return 0; mkdir -p "$(dirname "$backup_root/$relative")"; cp -a "$src" "$backup_root/$relative"; }

remove_global_block() {
  local target="$codex_home/AGENTS.md" begin_count end_count start end tmp total
  [[ -f "$target" ]] || { echo "未找到全局 AGENTS.md，跳过。"; return; }
  backup_path "$target" "codex/AGENTS.md"
  begin_count="$(grep -cF "$begin_marker" "$target" || true)"; end_count="$(grep -cF "$end_marker" "$target" || true)"
  [[ "$begin_count" -eq "$end_count" && "$begin_count" -le 1 ]] || { echo "AGENTS.md 受管标记异常，已停止卸载" >&2; exit 1; }
  [[ "$begin_count" -eq 1 ]] || { echo "AGENTS.md 中没有本包受管区块，跳过。"; return; }
  start="$(grep -nF "$begin_marker" "$target" | cut -d: -f1)"; end="$(grep -nF "$end_marker" "$target" | cut -d: -f1)"; total="$(wc -l < "$target")"; tmp="$(mktemp)"
  [[ "$start" -le 1 ]] || head -n $((start - 1)) "$target" >> "$tmp"
  [[ "$end" -ge "$total" ]] || tail -n +$((end + 1)) "$target" >> "$tmp"
  if grep -q '[^[:space:]]' "$tmp"; then
    awk 'BEGIN{b=0} /^[[:space:]]*$/{b++; if(b<=2) print; next} {b=0; print}' "$tmp" > "$target"
    echo "已移除本包 AGENTS.md 受管区块。"
  else rm -f "$target"; echo "已删除仅包含本包规则的 AGENTS.md。"; fi
  rm -f "$tmp"
}
remove_skills() { local n t; for n in "${managed_skills[@]}"; do t="$skills_home/$n"; [[ -e "$t" ]] || continue; backup_path "$t" "skills/$n"; rm -rf "$t"; echo "已卸载 Skill: $n"; done; }
remove_agents() { local n t; for n in "${managed_agents[@]}"; do t="$agents_home/$n"; [[ -e "$t" ]] || continue; backup_path "$t" "agents/$n"; rm -f "$t"; echo "已卸载 Reviewer: $n"; done; }

case "$component" in
  all) remove_global_block; remove_skills; remove_agents ;;
  skills) remove_skills ;;
  global) remove_global_block ;;
  agents) remove_agents ;;
esac

echo "卸载完成。其他规则、Skills 和自定义 Agent 未被删除。"
echo "备份目录: $backup_root"
