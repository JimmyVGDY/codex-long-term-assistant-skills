# V7.4.1 Release Notes

Version: 7.4.1  
Host window: Codex CLI 0.153.0 and the ten preceding stable releases

## Highlights

- Adds a closed `config/codex-compatibility-v1.json` registry that freezes eleven stable releases, official artifacts, capability profiles, and evidence states.
- Exercises Marketplace add, Plugin activation, JSON readback, and removal in an isolated `CODEX_HOME` before account writes, without copying real credentials.
- Upgrades install state to schema 3 and binds Codex version, CLI path and SHA-256, registry digest, capability digest, and payload digest.
- Makes `verify`, `status`, and `doctor` report `HOST_DRIFT_REINSTALL_REQUIRED` on version, executable, registry, or capability drift.
- Limits Marketplace ownership to the package name, display name, and target Plugin item while preserving unknown top-level data, nested `interface` data, `owner`, and other Plugins.
- Registers snake_case, camelCase, and compatibility Hook aliases. Security conflicts fail closed, observation conflicts become unavailable, and Stop/SubagentStop always return neutral JSON.
- Adds a Windows and Ubuntu release gate that replays every one of the eleven stable versions.

## Unchanged boundaries

- The V7.4.0 root-task budget, role weights, and parent-finalized calibration for Reviewer, Explorer, and Worker remain unchanged.
- The automatic ceiling remains `gpt-5.6-terra + high`; Sol, `xhigh`, `max`, and `ultra` are never selected automatically.
- Ordinary Hook fields are not trusted actual-model evidence. Prompts, answers, code, diffs, tokens, and credentials are not retained.
- Unregistered future, prerelease, and out-of-window hosts fail closed in Plugin mode; standalone mode remains an explicit fallback.

## Evidence boundary

The local isolated Windows matrix is not GitHub Ubuntu CI or a real account session. Full package validation, CI, independent review, and native 0.153.0 account and Hook evidence remain separate release gates.
