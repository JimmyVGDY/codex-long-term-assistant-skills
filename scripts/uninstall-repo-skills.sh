#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || { echo "用法: $0 /path/to/repo" >&2; exit 2; }
repo="$(cd "$1" && pwd)"
target_skills="$repo/.agents/skills"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$repo/.agents-backup-uninstall-$timestamp"
managed=(
  java-backend-engineering
  python-backend-ai-engineering
  vue-frontend-engineering
  data-middleware-ai-infrastructure
  engineering-quality-delivery
  technical-document-writing
  long-running-task-memory
)
for name in "${managed[@]}"; do
  target="$target_skills/$name"
  if [[ -d "$target" ]]; then
    mkdir -p "$backup_root"
    cp -a "$target" "$backup_root/$name"
    rm -rf "$target"
    echo "已卸载仓库级 Skill: $name"
  fi
done
echo "仓库级卸载完成，其他 Skills 未被删除。"
