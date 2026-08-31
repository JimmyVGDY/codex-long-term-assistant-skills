#!/usr/bin/env bash
set -euo pipefail

component="${1:-all}"
case "$component" in
  all|skills|global) ;;
  *) echo "用法: $0 [all|skills|global]" >&2; exit 2 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
source_global="$package_root/global/AGENTS.md"
source_skills="$package_root/skills"
codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$HOME/.codex-skill-backups/$timestamp"

backup_path() {
  local src="$1"
  local relative="$2"
  [[ -e "$src" ]] || return 0
  mkdir -p "$(dirname "$backup_root/$relative")"
  cp -a "$src" "$backup_root/$relative"
  echo "已备份: $src -> $backup_root/$relative"
}

install_global() {
  [[ -f "$source_global" ]] || { echo "缺少全局规则: $source_global" >&2; exit 1; }
  mkdir -p "$codex_home"
  backup_path "$codex_home/AGENTS.md" "codex/AGENTS.md"
  cp "$source_global" "$codex_home/AGENTS.md"
  echo "已安装全局规则: $codex_home/AGENTS.md"
}

install_skills() {
  [[ -d "$source_skills" ]] || { echo "缺少 Skills 目录: $source_skills" >&2; exit 1; }
  mkdir -p "$skills_home"
  for src in "$source_skills"/*; do
    [[ -d "$src" ]] || continue
    name="$(basename "$src")"
    target="$skills_home/$name"
    backup_path "$target" "skills/$name"
    rm -rf "$target"
    cp -a "$src" "$target"
    echo "已安装 Skill: $name"
  done
}

case "$component" in
  all) install_global; install_skills ;;
  skills) install_skills ;;
  global) install_global ;;
esac

echo
echo "安装完成。Codex 中运行 /skills 检查；未显示时重启 Codex。"
echo "全局规则目录: $codex_home"
echo "Skills 目录: $skills_home"
echo "备份目录: $backup_root"
