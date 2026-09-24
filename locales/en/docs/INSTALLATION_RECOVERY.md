<!-- Generated compatibility copy from locales/en/docs/operations/INSTALLATION_RECOVERY.md; edit that source and run scripts/documentation.py sync. -->

[Current location](operations/INSTALLATION_RECOVERY.md)

# V7.13.3 Installation, Validation, and Recovery

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/INSTALLATION_RECOVERY/)

## Preconditions

- Codex Desktop; management-component contracts and native task-runtime acceptance are separate.
- The base installation has no package Python-runtime prerequisite; only the enhancement runtime needs Python 3.11 or later.
- Extract the archive before running commands.
- Supported managed upgrades: <!-- cp-fact:upgrade-sources -->7.13.2, 7.13.1, 7.13.0, 7.12.0, 7.11.2, 7.11.1, 7.11.0, 7.10.0, 7.9.2, 7.9.1, 7.9.0, 7.8.1, 7.8.0, 7.7.1, 7.7.0, 7.6.2, 7.6.1, 7.6.0, 7.5.1, 7.5.0, 7.4.6, 7.4.5, 7.4.4, 7.4.3, 7.4.2, 7.4.1, 7.4.0, 7.3.0, 7.2.0, 7.1.0, 7.0.0, 6.6.1, 6.6.0, 6.5.0, 6.4.0, 6.3.0, 6.2.0, 6.1.0, 6.0.0, 5.1.0, 5.0.0, 4.2.0, 4.1.0, 4.0.0<!-- /cp-fact -->.
- A native Windows process uses a native Windows `CODEX_HOME`; WSL-style drive mappings are normalized before use.
- Unknown Skills, agents, Hooks, MCP configuration, Plugin files, and `config.toml` content remain outside managed deletion scope.

## Shortest usable path

Use the assistant directly after installation; the first full scan is optional. No reply, a declined scan, or unavailable auxiliary state keeps ordinary work on the current-source BASIC path. For recovery, run `doctor` for per-feature results, read-only `inventory` for managed, missing, drifted, and unknown assets, then canonical `recover` only when a durable transaction exists. `doctor --recover` is a compatibility alias for the same recovery function.

The daily entry is `scripts/cp-assistant.ps1`, `scripts/cp-assistant.sh`, or `scripts/cp-assistant.py`. It uses a whitelist and does not modify the global PATH. `help` and `install-base` do not depend on this package's Python. `status`, `doctor`, `inventory`, `verify`, and `resume` are query/verification actions; `install-base`, `install-enhancement`, and `recover` write managed state.

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py inventory --scope user --mode plugin --json
python scripts\package_manager.py recover --scope user
```

Equivalent unified-entry commands:

```powershell
.\scripts\cp-assistant.ps1 status
.\scripts\cp-assistant.ps1 doctor --json
.\scripts\cp-assistant.ps1 inventory --scope user --mode plugin --json
.\scripts\cp-assistant.ps1 resume --repo-path E:\\work\\repo --profile C:\\safe-state\\project-profile.json --state C:\\safe-state\\project-state.json --checkpoint-dir C:\\safe-state\\task --json
.\scripts\cp-assistant.ps1 recover --scope user
```

`resume` reads only the existing Project Profile/State, an explicit Markdown checkpoint directory, and explicitly supplied Evidence. It does not scan default user directories, create a binding, repair a ledger, mutate checkpoints, or invoke installation `recover`. Without a Profile, an explicit `--checkpoint-dir` is sufficient for the legacy Markdown mode. Unknown schemas, integrity failures, task/repository conflicts, and path escapes return structured failures. Repository changes, stale Evidence, exhausted read budgets, and missing checkpoints remain `UNKNOWN`, `PARTIAL`, or `STALE`; they are never projected as PASS. `resume --json` uses schema `resume-view/1`; complete queries exit 0, partial/unknown queries exit 1, and invalid-argument or integrity/identity failures exit 2.

Without state, `uninstall --dry-run` is a zero-delete preview and real uninstall still refuses. A non-Git directory retains basic documentation and file capabilities and is never initialized as a repository automatically.

Use `scripts\install-base.ps1` for the base installation (or `scripts/install-base.sh` on POSIX). It registers Skills only and rejects symbolic-link, Junction, and reparse-point ancestors before writing. A failed native Marketplace or Plugin registration rolls back the paths created by that attempt. If native registration cannot be removed, `cp-assistant-base-state.json` remains as `RECOVERY_REQUIRED`; the same base entry attempts managed recovery on the next run and never overwrites an unknown Marketplace.

## Upgrade sequence

The following Python commands add enhancements or upgrade an existing managed enhancement. Base-only users use the native base launcher above.

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
```

Dry-run acceptance requires prior-version detection, a bounded backup, contained destinations, rejected link and reparse ancestors, preserved unknown files, and a complete rollback plan.

The Desktop management contract uses top-level `interface.displayName` in a local Marketplace manifest. After backup, the upgrader writes its managed display name, preserves external fields including `owner`, and verifies managed-marketplace registration.

The base Plugin payload registers no Hooks. Enhancement installation registers optional observation and controlled-write Hooks in account-level `hooks.json`; `verify` checks this package's matcher, command, and event arguments while preserving third-party Hooks. An unknown version, a missing gate worker, or a drifted managed entry fails controlled-operation verification closed without preventing ordinary base tasks.

Plugin acceptance requires:

```ini
installed = true
enabled = true
version = 7.13.3
```

SessionEnd keeps a three-second host timeout. The Hook only constructs a capped, body-free sanitized event and dispatches a detached worker without waiting, using a command argument instead of a synchronous pipe; it does not scan or write the event chain. Stable-identity validation, semantic deduplication, persistence, DPAPI decryption, v2 signed enqueue, and sealing run in the worker outside the Hook budget. Evolution rejects an unsealed `seal_required` chain.

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, events, snapshots, assessments, and proposals remain preserved. Backup removal is a separate maintenance decision.

Run `validate-package.py` in the complete Git source checkout, not a single-language installation archive. `validate-package.py` invokes the current `validate-v74.py`, compares the Git index, tracked and untracked content, deletions, and link types before and after execution, and accepts `--output` only outside the repository. Package-only validation records `routing_host_observation=NOT_EVALUATED`; it does not prove host installation, Plugin registration, lifecycle execution, real-host routing, or effective state. Those states need separate readback evidence.

## Optional project gate and effective loading

Enhancement registration contains eight entry points, while the base Plugin contains none and project gates default to disabled. In V7.13.3, `UserPromptSubmit` is asynchronous observation, `Stop` is neutral observation, and `Interrupt` remains host-controlled. Canonical `apply_patch` advances Operation v2 through PreToolUse/PostToolUse only for an explicitly enabled policy; unconfigured or disabled policies remain neutral.

```text
Unconfigured or disabled ───────────────→ native writes preserve host behavior
Legacy enabled + native write tool ────→ deny LEGACY_WRITE_ORIGIN_UNAVAILABLE
UserPromptSubmit / Stop / Interrupt ───→ do not consume legacy GateTask control state
```

Configured `enabled=true`, a loaded enhancement, and semantic suitability are separate conclusions. V7.13.3 accepts only a Hook-created Operation v2 origin, permission claimed by a different B, and B's matching PostTool receipt; legacy GateTask receipts cannot authorize native writes. An open session can retain an older Plugin snapshot, so verify a fresh task after upgrade. Shell, MCP, and other entry points do not have guaranteed pre-write interception.

Current official Hook documentation and management-component probes provide separate interface evidence. Actual Desktop Hook loading and calls require independent readback. Frozen stable records serve historical recovery only. See the [capability index and workflow entry](CAPABILITY_INDEX.md) for legacy gate enable/disable entry points, but this patch does not restore the legacy task lifecycle as write authorization.

Internal routing entry: use `scripts/routing-v4.py` in the source package or `skills/multi-agent-independent-review/scripts/routing_v4.py` inside the installed independent-review Skill. Strict V4 requires the enhancement runtime and genuine Desktop binding; base mode reports policy constraints only.
