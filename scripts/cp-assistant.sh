#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command=${1:-help}
if [ "$#" -gt 0 ]; then shift; fi

case "$command" in
  help|--help|-h)
    printf '%s\n' 'Codex Cross Project Assistant daily entry' \
      'Usage: cp-assistant.sh <command> [options]' \
      'Commands: help, install-base, status, doctor, verify, inventory, install-enhancement, recover, resume' \
      'help and install-base do not require Python. Management commands require Python 3.11+.'
    exit 0
    ;;
  install-base)
    exec sh "$root/scripts/install-base.sh" "$@"
    ;;
esac

python_bin=${CP_ASSISTANT_PYTHON:-}
if [ -z "$python_bin" ]; then
  if command -v python3 >/dev/null 2>&1; then python_bin=$(command -v python3)
  elif command -v python >/dev/null 2>&1; then python_bin=$(command -v python)
  fi
fi
if [ -z "$python_bin" ]; then
  case " $* " in *' --json '*) printf '%s\n' '{"schema":"cp-assistant/1","overall":"UNKNOWN","reason":"PYTHON_REQUIRED","available":"Base Skill availability was not checked by this entry","next_action":"codex plugin list --json"}' ;; *) printf '%s\n' 'Python 3.11+ is required for this diagnostic command; run codex plugin list --json for native readback.' >&2 ;; esac
  exit 2
fi
exec "$python_bin" -B "$root/scripts/cp-assistant.py" "$command" "$@"
