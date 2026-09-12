#!/usr/bin/env sh
set -eu

package_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
codex_home=${CODEX_HOME:-"$HOME/.codex"}
base_state="$codex_home/cp-assistant-base-state.json"
market_root="$HOME/.agents/plugins/cp-assistant-base-marketplace"
plugin_root="$market_root/plugins/codex-cross-project-engineering-assistant"

fail() { printf '%s\n' "$*" >&2; exit 2; }

reject_link_ancestors() {
  current=$1
  case "$current" in /*) ;; *) fail "Managed path must be absolute: $current" ;; esac
  while :; do
    if [ -L "$current" ]; then
      fail "Managed path contains a symbolic-link ancestor: $current"
    fi
    parent=$(dirname -- "$current")
    [ "$parent" = "$current" ] && break
    current=$parent
  done
}

write_state() {
  status=$1
  mkdir -p "$codex_home"
  printf '%s\n' "{\"schema_version\":1,\"package\":\"codex-cross-project-engineering-assistant\",\"marketplace\":\"cp-assistant-base\",\"market_root\":\"$market_root\",\"status\":\"$status\"}" > "$base_state"
}

recover_partial() {
  reject_link_ancestors "$codex_home"
  reject_link_ancestors "$market_root"
  codex plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base' || fail 'Base recovery could not remove the registered Plugin; keep the recovery state and repair Codex registration first.'
  codex plugin marketplace remove 'cp-assistant-base' || fail 'Base recovery could not remove the registered Marketplace; keep the recovery state and repair Codex registration first.'
  if [ -e "$market_root" ]; then
    [ ! -L "$market_root" ] || fail "Base recovery refused linked Marketplace root: $market_root"
    rm -rf -- "$market_root"
  fi
  rm -f -- "$base_state"
}

if [ -e "$base_state" ]; then
  if grep -Fq '"package":"codex-cross-project-engineering-assistant"' "$base_state" \
    && grep -Fq '"marketplace":"cp-assistant-base"' "$base_state" \
    && grep -Fq "\"market_root\":\"$market_root\"" "$base_state" \
    && { grep -Fq '"status":"INSTALLING"' "$base_state" || grep -Fq '"status":"RECOVERY_REQUIRED"' "$base_state"; }; then
    recover_partial
  else
    printf '%s\n' 'Base Plugin is already installed by this entry; run install-user.sh for enhancements.' >&2
    exit 2
  fi
fi
if [ -e "$codex_home/cp-assistant-v6-state.json" ]; then
  printf '%s\n' 'A managed enhancement installation exists; refusing a base downgrade. Run install-user.sh.' >&2
  exit 2
fi

reject_link_ancestors "$package_root"
reject_link_ancestors "$codex_home"
reject_link_ancestors "$market_root"
if [ -e "$market_root" ]; then
  printf '%s\n' "Base Marketplace directory exists: $market_root. Refusing to overwrite unknown files." >&2
  exit 2
fi

committed=0
cleanup() {
  result=$?
  trap - 0
  if [ "$result" -ne 0 ] && [ "$committed" -ne 1 ] && [ -e "$base_state" ]; then
    if codex plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base' \
      && codex plugin marketplace remove 'cp-assistant-base'; then
      if [ -e "$market_root" ] && [ ! -L "$market_root" ]; then rm -rf -- "$market_root"; fi
      rm -f -- "$base_state"
    else
      write_state RECOVERY_REQUIRED
      printf '%s\n' 'Base installation failed; managed recovery state was retained because native registration cleanup did not complete.' >&2
    fi
  fi
  exit "$result"
}
trap cleanup 0

write_state INSTALLING
mkdir -p "$plugin_root" "$market_root/.agents/plugins"
cp -R "$package_root/.codex-plugin" "$package_root/skills" "$package_root/hooks" "$plugin_root/"
cat > "$market_root/.agents/plugins/marketplace.json" <<'JSON'
{
  "name": "cp-assistant-base",
  "interface": {"displayName": "Codex Cross Project Assistant"},
  "plugins": [{
    "name": "codex-cross-project-engineering-assistant",
    "source": {"source": "local", "path": "./plugins/codex-cross-project-engineering-assistant"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity"
  }]
}
JSON
codex plugin marketplace add "$market_root"
codex plugin add 'codex-cross-project-engineering-assistant@cp-assistant-base'
codex plugin list --json
write_state INSTALLED
committed=1
trap - 0
printf '%s\n' 'Base Plugin installed. Describe an engineering task directly; run install-user.sh for enhancements.'
