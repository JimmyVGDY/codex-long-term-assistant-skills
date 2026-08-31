#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 ]] || { echo "用法: $0 <repo-path> [--include-review-agents] [--no-backup]" >&2; exit 2; }
repo="$1"; shift
include_agents=0; no_backup=0
while [[ $# -gt 0 ]]; do case "$1" in --include-review-agents) include_agents=1 ;; --no-backup) no_backup=1 ;; *) echo "未知参数: $1" >&2; exit 2 ;; esac; shift; done
repo="$(cd "$repo" && pwd)"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; root="$(cd "$script_dir/.." && pwd)"
target_skills="$repo/.agents/skills"; target_agents="$repo/.codex/agents"; backup="$repo/.codex-skills-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$target_skills"
while IFS= read -r -d '' src; do name="$(basename "$src")"; target="$target_skills/$name"; if [[ -e "$target" && "$no_backup" -eq 0 ]]; then mkdir -p "$backup/skills"; cp -a "$target" "$backup/skills/$name"; fi; rm -rf "$target"; cp -a "$src" "$target"; echo "已安装仓库级 Skill: $name"; done < <(find "$root/skills" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
if [[ "$include_agents" -eq 1 ]]; then
  mkdir -p "$target_agents"
  while IFS= read -r -d '' src; do name="$(basename "$src")"; target="$target_agents/$name"; if [[ -e "$target" && "$no_backup" -eq 0 ]]; then mkdir -p "$backup/agents"; cp -a "$target" "$backup/agents/$name"; fi; cp "$src" "$target"; echo "已安装仓库级 Reviewer: $name"; done < <(find "$root/custom-agents" -maxdepth 1 -type f -name '*.toml' -print0 | sort -z)
fi
echo "Skills: $target_skills"
[[ "$include_agents" -eq 0 ]] || echo "Reviewers: $target_agents"
echo "这些目录位于仓库中，是否提交 Git 由项目规范决定。"
