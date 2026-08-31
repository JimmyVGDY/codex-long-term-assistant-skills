#!/usr/bin/env bash
set -euo pipefail

repo_path="${1:-}"
if [[ -z "$repo_path" ]]; then
  echo "用法: $0 /path/to/repository" >&2
  exit 2
fi
repo="$(cd "$repo_path" && pwd)"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
source_skills="$package_root/skills"
target_skills="$repo/.agents/skills"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$repo/.agents-backup-$timestamp"
mkdir -p "$target_skills"

for src in "$source_skills"/*; do
  [[ -d "$src" ]] || continue
  name="$(basename "$src")"
  target="$target_skills/$name"
  if [[ -e "$target" ]]; then
    mkdir -p "$backup_root"
    cp -a "$target" "$backup_root/$name"
  fi
  rm -rf "$target"
  cp -a "$src" "$target"
  echo "已安装仓库级 Skill: $name"
done

echo "仓库级 Skills 已安装到: $target_skills"
echo "注意：该目录位于仓库内，是否提交 Git 由项目规范决定。"
