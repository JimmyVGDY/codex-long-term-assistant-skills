#!/usr/bin/env bash
set -euo pipefail
repo="${1:?用法: install-repo-skills.sh /path/to/repo [--include-review-agents]}";shift||true;inc=0;[[ "${1:-}" == '--include-review-agents' ]]&&inc=1;repo=$(cd "$repo"&&pwd);sd=$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd);root=$(cd "$sd/.."&&pwd);t="$repo/.agents/skills";mkdir -p "$t";rm -rf "$t/vue-frontend-engineering";for x in "$root"/skills/*;do [[ -d "$x" ]]||continue;n=$(basename "$x");rm -rf "$t/$n";cp -a "$x" "$t/$n";done;if [[ $inc -eq 1 ]];then mkdir -p "$repo/.codex/agents";cp "$root"/custom-agents/*.toml "$repo/.codex/agents/";fi;echo '安装完成。'
