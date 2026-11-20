#!/usr/bin/env sh
set -eu
repo="${1:-.}"
shift 2>/dev/null || true
python3 "$(dirname "$0")/package_manager.py" install --scope repo --repo-path "$repo" "$@"
