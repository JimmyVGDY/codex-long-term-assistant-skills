#!/usr/bin/env sh
set -eu

package_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
codex_home=${CODEX_HOME:-"$HOME/.codex"}
desktop_component=${CP_ASSISTANT_DESKTOP_COMPONENT:-"$codex_home/plugins/.plugin-appserver/codex"}
base_state="$codex_home/cp-assistant-base-state.json"
market_root="$HOME/.agents/plugins/cp-assistant-base-marketplace"
plugin_root="$market_root/plugins/codex-cross-project-engineering-assistant"
market_manifest="$market_root/.agents/plugins/marketplace.json"
metadata="$package_root/scripts/base-registration.pl"

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

reject_payload_tree() {
  root=$1
  [ -e "$root" ] || [ -L "$root" ] || fail "Base payload is missing: $root"
  [ ! -L "$root" ] || fail "Base payload contains a symbolic link: $root"
  [ -d "$root" ] || fail "Base payload root is not a directory: $root"
  for item in "$root"/* "$root"/.[!.]* "$root"/..?*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    [ ! -L "$item" ] || fail "Base payload contains a symbolic link: $item"
    if [ -d "$item" ]; then
      reject_payload_tree "$item"
    fi
  done
}

registration() {
  if ! output=$("$desktop_component" plugin list --marketplace cp-assistant-base --json); then
    printf '%s\n' UNVERIFIED
    return
  fi
  printf '%s' "$output" | perl "$metadata" registration "$package_root"
}

confirm_registration() {
  observed=$(registration)
  [ "$observed" = "$1" ] && return 0
  case "$observed" in
    DISABLED) advice='The Plugin is disabled. Review its enabled setting in Codex Desktop.' ;;
    VERSION_MISMATCH) advice='A different version is registered. Use the managed upgrade path.' ;;
    MISSING|NOT_INSTALLED) advice='Inspect the installation in the Desktop Plugin list.' ;;
    IDENTITY_CONFLICT|ACTIVE) advice='Inspect the existing Plugin and its marketplace ownership.' ;;
    *) advice='Registration is unverified. Inspect the Plugin list in Codex Desktop.' ;;
  esac
  fail "BASE_REGISTRATION_$observed: $advice"
}

read_state() {
  if [ -e "$base_state" ]; then
    perl "$metadata" state-read "$base_state" "$market_root"
  else
    printf '%s\n' MISSING
  fi
}

write_state() {
  status=$1
  reject_link_ancestors "$base_state"
  mkdir -p "$codex_home"
  next_state=$(mktemp "$codex_home/.cp-assistant-base-state.XXXXXX") || return 1
  if perl "$metadata" state-write "$market_root" "$status" > "$next_state" && mv -f "$next_state" "$base_state"; then
    return 0
  fi
  rm -f -- "$next_state"
  return 1
}

remove_managed_tree() (
  source=$1
  target=$2
  reject_link_ancestors "$target"
  [ -e "$target" ] || [ -L "$target" ] || return 0
  [ ! -L "$target" ] || return 1
  if [ -d "$source" ]; then
    [ -d "$target" ] || return 1
    for item in "$source"/* "$source"/.[!.]* "$source"/..?*; do
      [ -e "$item" ] || [ -L "$item" ] || continue
      [ ! -L "$item" ] || return 1
      name=${item##*/}
      remove_managed_tree "$item" "$target/$name" || return 1
    done
    rmdir -- "$target" 2>/dev/null || true
    return 0
  fi
  [ ! -d "$target" ] || return 1
  cmp -s "$source" "$target" || return 1
  rm -f -- "$target"
)

remove_managed_manifest() {
  reject_link_ancestors "$market_manifest"
  [ -e "$market_manifest" ] || [ -L "$market_manifest" ] || return 0
  [ ! -L "$market_manifest" ] || return 1
  [ ! -d "$market_manifest" ] || return 1
  expected=$(mktemp "$codex_home/.cp-assistant-base-manifest.XXXXXX") || return 1
  cat > "$expected" <<'JSON'
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
  if cmp -s "$expected" "$market_manifest"; then
    rm -f -- "$market_manifest" "$expected"
  else
    rm -f -- "$expected"
    return 1
  fi
}

remove_empty_dir() {
  path=$1
  reject_link_ancestors "$path"
  [ -e "$path" ] || [ -L "$path" ] || return 0
  [ -d "$path" ] && [ ! -L "$path" ] || return 1
  rmdir -- "$path" 2>/dev/null || true
}

remove_managed_base() {
  reject_link_ancestors "$codex_home"
  reject_link_ancestors "$market_root"
  remove_managed_tree "$package_root/.codex-plugin" "$plugin_root/.codex-plugin" || return 1
  remove_managed_tree "$package_root/skills" "$plugin_root/skills" || return 1
  remove_managed_tree "$package_root/hooks" "$plugin_root/hooks" || return 1
  remove_managed_manifest || return 1
  remove_empty_dir "$plugin_root" || return 1
  [ ! -e "$plugin_root" ] || { printf '%s\n' "Unowned files occupy $plugin_root; preserving the files and recovery state." >&2; return 1; }
  remove_empty_dir "$market_root/plugins" || return 1
  remove_empty_dir "$market_root/.agents/plugins" || return 1
  remove_empty_dir "$market_root/.agents" || return 1
  remove_empty_dir "$market_root" || return 1
}

recover_partial() {
  reject_link_ancestors "$codex_home"
  reject_link_ancestors "$market_root"
  "$desktop_component" plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base' || fail 'Base recovery could not remove the registered Plugin; keep the recovery state and repair Codex registration first.'
  remove_market || fail 'Base recovery could not remove the registered Marketplace; keep the recovery state and repair Codex registration first.'
  remove_managed_base || fail 'Base recovery found drifted or unsafe managed assets; keep the recovery state and repair them explicitly.'
  rm -f -- "$base_state"
}

remove_market() {
  if message=$("$desktop_component" plugin marketplace remove 'cp-assistant-base' 2>&1); then return 0; fi
  case "$message" in
    *'marketplace '*cp-assistant-base*' is not configured or installed'*) [ "$(registration)" = MISSING ] ;;
    *) return 1 ;;
  esac
}

reject_link_ancestors "$base_state"
reject_link_ancestors "$codex_home/cp-assistant-v6-state.json"
[ -x "$desktop_component" ] || fail 'DESKTOP_COMPONENT_REQUIRED: start Codex Desktop or configure its bundled management component.'
if [ -e "$codex_home/cp-assistant-v6-state.json" ]; then
  printf '%s\n' 'A managed enhancement installation exists; refusing a base downgrade. Run install-user.sh.' >&2
  exit 2
fi

reject_link_ancestors "$package_root"
reject_link_ancestors "$codex_home"
reject_link_ancestors "$base_state"
reject_link_ancestors "$codex_home/cp-assistant-v6-state.json"
reject_link_ancestors "$market_root"
reject_link_ancestors "$plugin_root"
reject_link_ancestors "$market_manifest"
reject_payload_tree "$package_root/.codex-plugin"
reject_payload_tree "$package_root/skills"
reject_payload_tree "$package_root/hooks"
command -v perl >/dev/null 2>&1 && perl -MJSON::PP -MEncode -MFcntl -e 1 2>/dev/null ||
  fail 'BASE_REGISTRATION_UNVERIFIED: this entry needs Perl with JSON::PP to confirm registration. Inspect the Desktop Plugin list.'
phase=$(read_state) || fail 'BASE_STATE_INVALID: inspect the existing managed state.'
if [ "$phase" = INSTALLED ]; then
  confirm_registration ACTIVE
  printf '%s\n' 'Base Plugin is ready. Describe an engineering task in Codex Desktop.'
  exit 0
fi
lock="$codex_home/cp-assistant-v6.lock"
reject_link_ancestors "$lock"
mkdir -p "$codex_home"
exec 9>>"$lock"
perl "$metadata" lock || fail 'BASE_INSTALL_BUSY: retry when the current base installation finishes.'
[ ! -e "$codex_home/cp-assistant-v6-state.json" ] || fail 'A managed enhancement installation exists. Use the managed upgrade entry.'
[ ! -e "$codex_home/cp-assistant-v6-transaction.json" ] || fail 'An enhancement transaction needs recovery. Run cp-assistant recover --scope user.'
phase=$(read_state) || fail 'BASE_STATE_INVALID: inspect the existing managed state.'
case "$phase" in
  INSTALLED) confirm_registration ACTIVE; printf '%s\n' 'Base Plugin is ready.'; exit 0 ;;
  INSTALLING|RECOVERY_REQUIRED) write_state RECOVERY_REQUIRED; recover_partial ;;
esac
confirm_registration MISSING
if [ -e "$market_root" ] && [ ! -d "$market_root" ]; then
  printf '%s\n' "Base Marketplace path is not a directory: $market_root. Refusing to overwrite unknown files." >&2
  exit 2
fi
if [ -e "$plugin_root" ] || [ -L "$plugin_root" ]; then
  printf '%s\n' "Base Plugin payload directory exists: $plugin_root. Refusing to overwrite unknown files." >&2
  exit 2
fi
if [ -e "$market_manifest" ] || [ -L "$market_manifest" ]; then
  printf '%s\n' "Base Marketplace manifest exists: $market_manifest. Refusing to overwrite unknown files." >&2
  exit 2
fi

committed=0
cleanup() {
  result=$?
  trap - 0
  if [ "$result" -ne 0 ] && [ "$committed" -ne 1 ] && [ -e "$base_state" ]; then
    if "$desktop_component" plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base' \
      && remove_market; then
      if remove_managed_base && rm -f -- "$base_state"; then
        :
      else
        write_state RECOVERY_REQUIRED
        printf '%s\n' 'Base installation failed; managed recovery state was retained because managed cleanup did not complete.' >&2
      fi
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
reject_link_ancestors "$plugin_root"
reject_link_ancestors "$market_manifest"
cp -R "$package_root/.codex-plugin" "$package_root/skills" "$package_root/hooks" "$plugin_root/"
cat > "$market_manifest" <<'JSON'
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
"$desktop_component" plugin marketplace add "$market_root"
"$desktop_component" plugin add 'codex-cross-project-engineering-assistant@cp-assistant-base'
confirm_registration ACTIVE
write_state INSTALLED
committed=1
trap - 0
printf '%s\n' 'Base Plugin installed. Describe an engineering task directly; run install-user.sh for enhancements.'
