# V7.1 Installation, Validation, and Recovery

## Preconditions

- Native Windows Codex CLI 0.152.1.
- The archive is extracted before any command runs.
- Supported managed upgrades: 7.0.0, 6.6.1, 6.6.0, 6.5.0, 6.4.0, 6.3.0, 6.2.0, 6.1.0, 6.0.0, 5.1.0, 5.0.0, 4.2.0, 4.1.0, and 4.0.0.
- A Windows-native process must use a Windows-native `CODEX_HOME`. A value such as `/mnt/c/Users/HP/.codex` is converted to the equivalent drive path and is never used literally.
- Unknown Skills, agents, Hooks, MCP configuration, Plugin files, and `config.toml` content remain outside the managed deletion scope.

## Upgrade sequence

Run from the extracted language-package root:

```powershell
codex --version
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

Dry-run acceptance requires detection of the prior managed installation, a bounded backup, contained destination paths, rejection of link and reparse ancestors, preservation of unknown files, and a complete rollback plan.

Plugin acceptance requires all three values:

```ini
installed = true
enabled = true
version = 7.1.0
```

## Recovery boundary

The installer journals managed changes and restores the pre-upgrade state when a managed installation step fails. It never removes an entire `.codex`, `.agents`, or plugins directory. Existing project context, TaskOutcomeEvent records, snapshots, assessments, and proposals remain preserved.

Backup retention is intentional after successful validation. Removal is a separate maintenance decision.

## Package validation

```powershell
python scripts\validate-v71.py
python scripts\build-release.py verify --archive ..\Codex-Skills-V7.1.0-en.zip --locale en
```

Package-only validation does not prove host installation, Plugin registration, lifecycle execution, or effective state. Those states need separate readback evidence.
