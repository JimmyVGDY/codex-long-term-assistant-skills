# V7.8 Installation, Validation, and Recovery

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/INSTALLATION_RECOVERY/)

## Preconditions

- Native Windows Codex CLI 0.154.0.
- Python 3.11 or later.
- Extract the archive before running commands.
- Supported managed upgrades: <!-- cp-fact:upgrade-sources -->7.7.1, 7.7.0, 7.6.2, 7.6.1, 7.6.0, 7.5.1, 7.5.0, 7.4.6, 7.4.5, 7.4.4, 7.4.3, 7.4.2, 7.4.1, 7.4.0, 7.3.0, 7.2.0, 7.1.0, 7.0.0, 6.6.1, 6.6.0, 6.5.0, 6.4.0, 6.3.0, 6.2.0, 6.1.0, 6.0.0, 5.1.0, 5.0.0, 4.2.0, 4.1.0, 4.0.0<!-- /cp-fact -->.
- A native Windows process uses a native Windows `CODEX_HOME`; WSL-style drive mappings are normalized before use.
- Unknown Skills, agents, Hooks, MCP configuration, Plugin files, and `config.toml` content remain outside managed deletion scope.

## Shortest usable path

Use the assistant directly after installation; the first full scan is optional. No reply, a declined scan, or unavailable auxiliary state keeps ordinary work on the current-source BASIC path. For recovery, run `doctor` for per-feature results, read-only `inventory` for managed, missing, drifted, and unknown assets, then canonical `recover` only when a durable transaction exists. `doctor --recover` is a compatibility alias for the same recovery function.

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py inventory --scope user --mode plugin --json
python scripts\package_manager.py recover --scope user
```

Without state, `uninstall --dry-run` is a zero-delete preview and real uninstall still refuses. A non-Git directory retains basic documentation and file capabilities and is never initialized as a repository automatically.

## Upgrade sequence

```powershell
codex --version
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

Dry-run acceptance requires prior-version detection, a bounded backup, contained destinations, rejected link and reparse ancestors, preserved unknown files, and a complete rollback plan.

Codex 0.154.0 requires top-level `interface.displayName` in a local Marketplace manifest. After backup, the upgrader removes the legacy `owner`, writes a controlled `interface.displayName`, preserves other unknown external fields, and proceeds only after `codex plugin list --json` recovers.

The Plugin payload statically registers UserPromptSubmit with `async=true`. The installer therefore must first match the current Codex CLI exactly to the frozen compatibility window and validate that version's bound official repository, tag, commit, source path, and SHA-256. An unknown version or incomplete evidence fails closed before any account file is written; standalone mode uses the same capability profile to omit the optional UserPromptSubmit registration dynamically.

Plugin acceptance requires:

```ini
installed = true
enabled = true
version = 7.8.0
```

SessionEnd keeps a three-second host timeout. The Hook only constructs a capped, body-free sanitized event and dispatches a detached worker without waiting, using a command argument instead of a synchronous pipe; it does not scan or write the event chain. Stable-identity validation, semantic deduplication, persistence, DPAPI decryption, v2 signed enqueue, and sealing run in the worker outside the Hook budget. Evolution rejects an unsealed `seal_required` chain.

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, events, snapshots, assessments, and proposals remain preserved. Backup removal is a separate maintenance decision.

Run `validate-package.py` in the complete Git source checkout, not a single-language installation archive. `validate-package.py` invokes the current `validate-v74.py`, compares the Git index, tracked and untracked content, deletions, and link types before and after execution, and accepts `--output` only outside the repository. Package-only validation records `routing_host_observation=NOT_EVALUATED`; it does not prove host installation, Plugin registration, lifecycle execution, real-host routing, or effective state. Those states need separate readback evidence.

## Optional project gate and effective loading

The registration contains eight entry points, while project gates default to disabled. In V7.8.0, `UserPromptSubmit` is asynchronous observation, `Stop` is neutral observation, and `Interrupt` remains host-controlled. Canonical `apply_patch` advances Operation v2 through PreToolUse/PostToolUse only for an explicitly enabled policy; unconfigured or disabled policies remain neutral.

```text
Unconfigured or disabled ───────────────→ native writes preserve host behavior
Legacy enabled + native write tool ────→ deny LEGACY_WRITE_ORIGIN_UNAVAILABLE
UserPromptSubmit / Stop / Interrupt ───→ do not consume legacy GateTask control state
```

Configured `enabled=true`, a loaded Plugin, and semantic suitability are separate conclusions. V7.8.0 accepts only a Hook-created Operation v2 origin, permission claimed by a different B, and B's matching PostTool receipt; legacy GateTask receipts cannot authorize native writes. An open session can retain an older Plugin snapshot, so verify a fresh task after upgrade. Shell, MCP, and other entry points do not have guaranteed pre-write interception.

All 11 Codex CLI versions in the frozen window have per-version official source evidence for UserPromptSubmit async behavior; Desktop and other real hosts still require separate readback. See the [capability index and workflow entry](../CAPABILITY_INDEX.md) for legacy gate enable/disable entry points, but this patch does not restore the legacy task lifecycle as write authorization.
