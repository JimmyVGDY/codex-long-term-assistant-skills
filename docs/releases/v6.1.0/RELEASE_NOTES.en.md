# V6.1 Official Plugin Installation Compatibility Release

V6.1 builds on V6.0 and fixes compatibility with the actual Plugin, Marketplace, and Hook loading mechanisms in Codex CLI 0.150.1.

## Fixes

- The Marketplace manifest now uses the `.agents/plugins/marketplace.json` layout supported by Codex 0.150.1.
- In Plugin mode, the installer actually runs `codex plugin marketplace add <root>` and `codex plugin add <plugin>@<marketplace>`.
- `verify --mode plugin` no longer treats copied files as proof of installation. It reads `codex plugin list --json` and requires both `installed=true` and `enabled=true`.
- Plugin Hooks provide both the Unix `command` and Windows `commandWindows` forms, avoiding the inability of `cmd.exe` to expand `$PLUGIN_ROOT`.
- The `SessionEnd` timeout is set to three seconds, matching the current Codex host limit.
- V6 retains its 10 Skills, 7 Reviewers, TaskOutcomeEvent V2, Terra High automatic-subagent ceiling, and controlled-evolution authorization boundaries.
- When native Windows Python inherits a WSL-style `/mnt/c/...` value for `CODEX_HOME`, the installer converts it to a native drive path before performing safety checks.
- If Plugin installation fails, the installer reverses any partial Plugin registration and cleans up the installation state. Plugin uninstall calls `codex plugin remove` before restoring managed files.
