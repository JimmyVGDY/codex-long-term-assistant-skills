#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 ]] || { echo "用法: $0 <repo-path> [--include-review-agents] [--no-backup]" >&2; exit 2; }
repo="$1"; shift
include_agents=0; no_backup=0
while [[ $# -gt 0 ]]; do case "$1" in --include-review-agents) include_agents=1 ;; --no-backup) no_backup=1 ;; *) echo "未知参数: $1" >&2; exit 2 ;; esac; shift; done
repo="$(cd "$repo" && pwd)"; skills="$repo/.agents/skills"; agents="$repo/.codex/agents"; backup="$repo/.codex-skills-backup-uninstall-$(date +%Y%m%d-%H%M%S)"
managed_skills=(java-backend-engineering python-backend-ai-engineering vue-frontend-engineering data-middleware-ai-infrastructure log-observability-analysis engineering-quality-delivery multi-agent-independent-review technical-document-writing long-running-task-memory)
managed_agents=(cp-review-functional-business.toml cp-review-compatibility-regression.toml cp-review-security-access.toml cp-review-performance-resources.toml cp-review-data-contract.toml cp-review-state-concurrency.toml cp-review-test-delivery.toml)
for n in "${managed_skills[@]}"; do t="$skills/$n"; [[ -e "$t" ]] || continue; if [[ "$no_backup" -eq 0 ]]; then mkdir -p "$backup/skills"; cp -a "$t" "$backup/skills/$n"; fi; rm -rf "$t"; echo "已卸载仓库级 Skill: $n"; done
if [[ "$include_agents" -eq 1 ]]; then for n in "${managed_agents[@]}"; do t="$agents/$n"; [[ -e "$t" ]] || continue; if [[ "$no_backup" -eq 0 ]]; then mkdir -p "$backup/agents"; cp -a "$t" "$backup/agents/$n"; fi; rm -f "$t"; echo "已卸载仓库级 Reviewer: $n"; done; fi
echo "仓库级卸载完成，其他 Skills 和 Agent 未被删除。"
