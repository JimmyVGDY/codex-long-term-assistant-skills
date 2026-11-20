#!/usr/bin/env sh
set -eu
python3 "$(dirname "$0")/package_manager.py" install --scope user --mode "${CP_INSTALL_MODE:-plugin}" "$@"
