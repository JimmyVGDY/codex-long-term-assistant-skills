#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command=${1:-help}
if [ "$#" -gt 0 ]; then shift; fi

case "$command" in
  help|--help|-h)
    printf '%s\n' 'Codex 跨项目助手日常入口' \
      'Usage: cp-assistant.sh <command> [options]' \
      'Commands: help, install-base, status, doctor, verify, inventory, install-enhancement, recover, resume' \
      'help 与 install-base 无需 Python；管理命令需要 Python 3.11+。'
    exit 0
    ;;
  install-base)
    if [ "$#" -gt 0 ]; then
      if [ "$#" -eq 1 ] && { [ "$1" = '--help' ] || [ "$1" = '-h' ]; }; then
        printf '%s\n' 'Usage: cp-assistant.sh install-base (writes the managed base installation)'
        exit 0
      fi
      printf '%s\n' '[ERROR] install-base does not accept extra arguments' >&2
      exit 2
    fi
    exec sh "$root/scripts/install-base.sh" "$@"
    ;;
  status|doctor|verify|inventory|install-enhancement|recover|resume) ;;
  *) printf '%s\n' '[ERROR] unknown cp-assistant command' >&2; exit 2 ;;
esac

python_bin=${CP_ASSISTANT_PYTHON:-}
supports_python() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)' >/dev/null 2>&1
}
if [ -n "$python_bin" ]; then
  if ! supports_python "$python_bin"; then python_bin=; fi
else
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && supports_python "$candidate"; then
      python_bin=$(command -v "$candidate")
      break
    fi
  done
fi
if [ -z "$python_bin" ]; then
  case " $* " in *' --json '*) printf '%s\n' '{"schema":"cp-assistant/1","overall":"UNKNOWN","reason":"PYTHON_REQUIRED","available":"Base Skill availability was not checked by this entry","next_action":"codex plugin list --json"}' ;; *) printf '%s\n' 'Python 3.11+ is required for this diagnostic command; run codex plugin list --json for native readback.' >&2 ;; esac
  exit 2
fi
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 exec "$python_bin" -B "$root/scripts/cp-assistant.py" "$command" "$@"
