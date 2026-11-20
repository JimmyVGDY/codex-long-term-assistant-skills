#!/usr/bin/env sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$#" in
  0) exec sh "$script_dir/cp-assistant.sh" recover --scope user ;;
  1) if [ "$1" = '--help' ] || [ "$1" = '-h' ]; then
       exec sh "$script_dir/cp-assistant.sh" recover --help
     fi ;;
esac
printf '%s\n' 'This entry recovers the current user transaction. For other scopes or options use cp-assistant recover.' >&2
exit 2
