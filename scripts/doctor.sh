#!/usr/bin/env bash
set -euo pipefail
if command -v python3 >/dev/null 2>&1; then PY=python3; elif command -v python >/dev/null 2>&1; then PY=python; else echo "[FAIL] 未找到 Python 3" >&2; exit 1; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PY" "$SCRIPT_DIR/package_manager.py" doctor
