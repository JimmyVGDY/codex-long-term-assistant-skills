# V6.6.1 Installation, Validation, and Recovery

中文：[`INSTALLATION_RECOVERY.md`](INSTALLATION_RECOVERY.md)

## Preconditions

- Native Windows Codex CLI 0.150.1.
- Extract the archive before running commands.
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

Plugin acceptance requires:

```ini
installed = true
enabled = true
version = 6.6.1
```

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, events, snapshots, assessments, and proposals remain preserved. Backup removal is a separate maintenance decision.

Package-only validation does not prove host installation, Plugin registration, lifecycle execution, or effective state. Those states need separate readback evidence.
