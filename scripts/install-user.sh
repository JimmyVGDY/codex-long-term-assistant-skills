#!/usr/bin/env bash
set -euo pipefail

component="all"
force_replace_global=0
no_backup=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    all|skills|global) component="$1" ;;
    --force-replace-global) force_replace_global=1 ;;
    --no-backup) no_backup=1 ;;
    -h|--help)
      echo "用法: $0 [all|skills|global] [--force-replace-global] [--no-backup]"
      exit 0
      ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
source_global="$package_root/global/AGENTS.md"
source_skills="$package_root/skills"
codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_home="$HOME/.agents/skills"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$HOME/.codex-skill-backups/$timestamp"
begin_marker='<!-- codex-cross-project-assistant:begin -->'
end_marker='<!-- codex-cross-project-assistant:end -->'

backup_path() {
  local src="$1"
  local relative="$2"
  [[ "$no_backup" -eq 1 || ! -e "$src" ]] && return 0
  mkdir -p "$(dirname "$backup_root/$relative")"
  cp -a "$src" "$backup_root/$relative"
  echo "已备份: $src -> $backup_root/$relative"
}

merge_global_file() {
  local target="$1"
  local source="$2"
  local tmp
  tmp="$(mktemp)"

  local begin_count end_count
  begin_count="$(grep -cF "$begin_marker" "$target" || true)"
  end_count="$(grep -cF "$end_marker" "$target" || true)"

  if [[ "$begin_count" -ne "$end_count" || "$begin_count" -gt 1 ]]; then
    rm -f "$tmp"
    echo "现有 AGENTS.md 的受管标记不完整或重复，已停止安装: $target" >&2
    exit 1
  fi

  if [[ "$begin_count" -eq 0 ]]; then
    cat "$target" > "$tmp"
    [[ ! -s "$target" || "$(tail -c 1 "$target" 2>/dev/null || true)" == $'\n' ]] || echo >> "$tmp"
    echo >> "$tmp"
    cat "$source" >> "$tmp"
  else
    local start end
    start="$(grep -nF "$begin_marker" "$target" | head -n 1 | cut -d: -f1)"
    end="$(grep -nF "$end_marker" "$target" | head -n 1 | cut -d: -f1)"
    if [[ "$start" -gt "$end" ]]; then
      rm -f "$tmp"
      echo "现有 AGENTS.md 的受管标记顺序错误，已停止安装: $target" >&2
      exit 1
    fi
    if [[ "$start" -gt 1 ]]; then head -n $((start - 1)) "$target" >> "$tmp"; fi
    cat "$source" >> "$tmp"
    local total
    total="$(wc -l < "$target")"
    if [[ "$end" -lt "$total" ]]; then tail -n +$((end + 1)) "$target" >> "$tmp"; fi
  fi

  mv "$tmp" "$target"
}

install_global() {
  [[ -f "$source_global" ]] || { echo "缺少全局规则: $source_global" >&2; exit 1; }
  grep -qF "$begin_marker" "$source_global" || { echo "安装包全局规则缺少开始标记" >&2; exit 1; }
  grep -qF "$end_marker" "$source_global" || { echo "安装包全局规则缺少结束标记" >&2; exit 1; }

  mkdir -p "$codex_home"
  local target="$codex_home/AGENTS.md"
  backup_path "$target" "codex/AGENTS.md"

  if [[ "$force_replace_global" -eq 1 || ! -f "$target" ]]; then
    cp "$source_global" "$target"
    echo "已安装全局规则（完整写入）: $target"
  else
    merge_global_file "$target" "$source_global"
    echo "已更新或追加 AGENTS.md 的本包受管区块，其他规则保持不变: $target"
  fi
}

install_skills() {
  [[ -d "$source_skills" ]] || { echo "缺少 Skills 目录: $source_skills" >&2; exit 1; }
  mkdir -p "$skills_home"
  while IFS= read -r -d '' src; do
    local name target
    name="$(basename "$src")"
    target="$skills_home/$name"
    backup_path "$target" "skills/$name"
    rm -rf "$target"
    cp -a "$src" "$target"
    echo "已安装 Skill: $name"
  done < <(find "$source_skills" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
}

case "$component" in
  all) install_global; install_skills ;;
  skills) install_skills ;;
  global) install_global ;;
esac

echo
echo "安装完成。请在 Codex 中运行 /skills；未刷新时重启 Codex。"
echo "全局规则目录: $codex_home"
echo "Skills 目录: $skills_home"
[[ "$no_backup" -eq 1 ]] || echo "备份目录: $backup_root"
