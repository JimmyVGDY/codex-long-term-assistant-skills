#!/usr/bin/env bash
set -euo pipefail
component="${1:-all}"; case "$component" in all|skills|global|agents) ;; *) echo "用法: $0 [all|skills|global|agents]" >&2; exit 2;; esac
sd="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";root="$(cd "$sd/.."&&pwd)";ch="${CODEX_HOME:-$HOME/.codex}";skills="$HOME/.agents/skills";agents="$ch/agents";ts="$(date +%Y%m%d-%H%M%S)";backup="$HOME/.codex-skill-backups/$ts";b='<!-- codex-cross-project-assistant:begin -->';e='<!-- codex-cross-project-assistant:end -->'
bk(){ [[ -e "$1" ]]||return 0; mkdir -p "$(dirname "$backup/$2")";cp -a "$1" "$backup/$2";}
g(){ mkdir -p "$ch";t="$ch/AGENTS.md";bk "$t" codex/AGENTS.md;if [[ ! -f "$t" ]];then cp "$root/global/AGENTS.md" "$t";else bc=$(grep -cF "$b" "$t"||true);ec=$(grep -cF "$e" "$t"||true);[[ $bc -eq $ec && $bc -le 1 ]]||{ echo 'AGENTS.md 受管标记异常' >&2;exit 1;};tmp=$(mktemp);if [[ $bc -eq 0 ]];then cat "$t">"$tmp";printf '

'>>"$tmp";cat "$root/global/AGENTS.md">>"$tmp";else awk -v src="$root/global/AGENTS.md" -v b="$b" -v e="$e" 'function p(l){while((getline l<src)>0)print l;close(src)} $0==b{p();skip=1;next} $0==e{skip=0;next} !skip{print}' "$t">"$tmp";fi;mv "$tmp" "$t";fi;}
s(){ mkdir -p "$skills";if [[ -d "$skills/vue-frontend-engineering" ]];then bk "$skills/vue-frontend-engineering" deprecated-skills/vue-frontend-engineering;rm -rf "$skills/vue-frontend-engineering";fi;for x in "$root"/skills/*;do [[ -d "$x" ]]||continue;n=$(basename "$x");bk "$skills/$n" "skills/$n";rm -rf "$skills/$n";cp -a "$x" "$skills/$n";done;}
a(){ mkdir -p "$agents";for x in "$root"/custom-agents/*.toml;do [[ -f "$x" ]]||continue;n=$(basename "$x");bk "$agents/$n" "agents/$n";cp "$x" "$agents/$n";done;}
case "$component" in all)g;s;a;;skills)s;;global)g;;agents)a;;esac
echo '安装完成。请重启 Codex 并运行 /skills。'
