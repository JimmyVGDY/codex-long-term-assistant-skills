<!-- Generated from locales/en/docs/operations/INSTALLATION_RECOVERY.md; edit that source and run scripts/documentation.py sync. -->

# V7.6 Installation, Validation, and Recovery

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/INSTALLATION_RECOVERY/)

## Preconditions

- Native Windows Codex CLI 0.153.4.
- Python 3.11 or later.
- Extract the archive before running commands.
- Supported managed upgrades: <!-- cp-fact:upgrade-sources -->7.6.0, 7.5.1, 7.5.0, 7.4.6, 7.4.5, 7.4.4, 7.4.3, 7.4.2, 7.4.1, 7.4.0, 7.3.0, 7.2.0, 7.1.0, 7.0.0, 6.6.1, 6.6.0, 6.5.0, 6.4.0, 6.3.0, 6.2.0, 6.1.0, 6.0.0, 5.1.0, 5.0.0, 4.2.0, 4.1.0, 4.0.0<!-- /cp-fact -->.
- A native Windows process uses a native Windows `CODEX_HOME`; WSL-style drive mappings are normalized before use.
- Unknown Skills, agents, Hooks, MCP configuration, Plugin files, and `config.toml` content remain outside managed deletion scope.

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

Codex 0.153.4 requires top-level `interface.displayName` in a local Marketplace manifest. After backup, the upgrader removes the legacy `owner`, writes a controlled `interface.displayName`, preserves other unknown external fields, and proceeds only after `codex plugin list --json` recovers.

Plugin acceptance requires:

```ini
installed = true
enabled = true
version = 7.6.1
```

SessionEnd keeps a three-second host timeout. The Hook only constructs a capped, body-free sanitized event and dispatches a detached worker without waiting, using a command argument instead of a synchronous pipe; it does not scan or write the event chain. Stable-identity validation, semantic deduplication, persistence, DPAPI decryption, v2 signed enqueue, and sealing run in the worker outside the Hook budget. Evolution rejects an unsealed `seal_required` chain.

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, events, snapshots, assessments, and proposals remain preserved. Backup removal is a separate maintenance decision.

Run `validate-package.py` in the complete Git source checkout, not a single-language installation archive. `validate-package.py` invokes the current `validate-v74.py`, compares the Git index, tracked and untracked content, deletions, and link types before and after execution, and accepts `--output` only outside the repository. Package-only validation records `routing_host_observation=NOT_EVALUATED`; it does not prove host installation, Plugin registration, lifecycle execution, real-host routing, or effective state. Those states need separate readback evidence.

## Optional project gate and effective loading

The registration contains seven entry points, while project gates default to disabled. Once enabled, `UserPromptSubmit` establishes the real task origin, `PreToolUse` checks preparation for controlled writes, `Stop` rechecks current finish evidence, and `Interrupt` records cancellation. The six-event observation chain remains separate.

```text
Explicit project opt-in → host loading → real task origin
                                         ↓
Bounded scan / query → prepare → development and validation → finish → check
                        └─ Interrupt → CANCELLED
```

Configured `enabled=true`, loaded Plugin, workflow PASS, and semantic suitability are separate conclusions. An already-open session can retain an older snapshot. A missing real session/turn origin cannot be fabricated by CLI or borrowed from another task. Cancellation is terminal for that task. Entry points outside controlled write tools do not have guaranteed pre-write interception.

Codex CLI 0.153.4 has real UserPromptSubmit/Interrupt acceptance evidence; the observed 0.149.1 configuration path ignores Interrupt. Six-event compatibility evidence does not prove cancellation support, and Desktop or other hosts require separate readback. See the [capability index and workflow entry](../CAPABILITY_INDEX.en.md) for enable, disable, prepare, and finish operations.
