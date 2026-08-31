# V6.1 Final Validation Report

- Target version: 6.1.0
- Codex compatibility target: 0.150.1
- Python syntax compilation: PASS
- Unit and regression tests: 20/20 PASS
- `scripts/validate-package.py`: PASS
- Skills: 10
- Reviewers: 7
- Hooks: 6 (UserPromptSubmit, PreToolUse, SubagentStart, SubagentStop, Stop, SessionEnd)
- TaskOutcomeEvent: 2.0
- `execution_authorization`: NONE
- Automatic self-modification: disabled
- Routing-case schema: 35 cases PASS
- Plugin installation transaction: PASS with simulated Codex 0.150.1 CLI
- Plugin verify: PASS, including installed and enabled
- Plugin uninstall and Marketplace cleanup: PASS
- Standalone install, verify, and uninstall: PASS
- Native Windows conversion of WSL-style CODEX_HOME: implemented
- Real native-Windows Codex 0.150.1 end-to-end: requires acceptance after installation on the target machine

## Key V6.1 Repairs

1. Marketplace manifest uses the `.agents/plugins/marketplace.json` layout supported by Codex 0.150.1.
2. Plugin-mode installer invokes `codex plugin marketplace add <root>` and `codex plugin add <plugin>@<marketplace>`.
3. Plugin verify uses `codex plugin list --json` to check installed and enabled instead of only copied files.
4. Hooks configure both `command` and `commandWindows`; Windows no longer requires a separately created `python3.exe`.
5. SessionEnd timeout is fixed at three seconds to match the Codex 0.150.1 host limit.
6. If native Windows Python inherits a `/mnt/c/...` CODEX_HOME, it converts the path to a native drive-letter path before safety checks.
7. Plugin installation failure reverses partial registration and restores old state. Uninstall removes Plugin and Marketplace registration and restores the old version during upgrade rollback.
