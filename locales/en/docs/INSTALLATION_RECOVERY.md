# V7.4 Installation, Validation, and Recovery

Chinese: [`INSTALLATION_RECOVERY.md`](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/INSTALLATION_RECOVERY/)

## Preconditions

- Native Windows Codex CLI 0.153.2.
- Python 3.11 or later.
- Extract the archive before running commands.
- Supported managed upgrades: 7.3.0, 7.2.0, 7.1.0, 7.0.0, 6.6.1, 6.6.0, 6.5.0, 6.4.0, 6.3.0, 6.2.0, 6.1.0, 6.0.0, 5.1.0, 5.0.0, 4.2.0, 4.1.0, and 4.0.0.
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

Codex 0.153.2 requires top-level `interface.displayName` in a local Marketplace manifest. After backup, the upgrader removes the legacy `owner`, writes a controlled `interface.displayName`, preserves other unknown external fields, and proceeds only after `codex plugin list --json` recovers.

Plugin acceptance requires:

```ini
installed = true
enabled = true
version = 7.4.2
```

SessionEnd keeps a three-second host timeout. The Hook only constructs a capped, body-free sanitized event and dispatches a detached worker without waiting, using a command argument instead of a synchronous pipe; it does not scan or write the event chain. Stable-identity validation, semantic deduplication, persistence, DPAPI decryption, v2 signed enqueue, and sealing run in the worker outside the Hook budget. Evolution rejects an unsealed `seal_required` chain.

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, events, snapshots, assessments, and proposals remain preserved. Backup removal is a separate maintenance decision.

`validate-package.py` invokes the current `validate-v74.py`, compares the Git index, tracked and untracked content, deletions, and link types before and after execution, and accepts `--output` only outside the repository. Package-only validation records `routing_host_observation=NOT_EVALUATED`; it does not prove host installation, Plugin registration, lifecycle execution, real-host routing, or effective state. Those states need separate readback evidence.
