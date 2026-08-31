# V6.1 Review and Repair Report

## Baseline

This review compares the V6.0 package with the actual Windows installation report. V6.0 ultimately achieved real loading of its Plugin, 6 Hooks, 10 Skills, and 7 Reviewers through manual compatibility work. The same process exposed problems involving `python3.exe`, the Marketplace manifest layout, and an installer that only instructed the operator to register the Plugin later.

## V6.1 Repairs

1. Changed the Marketplace layout to `.agents/plugins/marketplace.json`.
2. The Plugin installer now calls Codex CLI directly to register the Marketplace and run `plugin add`.
3. Verify reads `codex plugin list --json` and requires installed+enabled.
4. Hooks use both `commandWindows` and `command`; Windows no longer depends on a manually created `python3.exe`.
5. SessionEnd timeout is three seconds.
6. Controlled evolution and the Terra High ceiling are retained.
7. When native Windows Python inherits a WSL-style `/mnt/c/...` value for `CODEX_HOME`, the installer converts it to a native drive path before safety checks.
8. Failed Plugin installation reverses possible partial registration and removes the state file. Plugin uninstall calls `codex plugin remove` before restoring managed files.

## Real-Host Acceptance Still Required

- First-use Hook trust UI in Codex 0.150.1.
- The six-Hook lifecycle under native Windows CLI.
- PreToolUse denial for a real automatic subagent.
