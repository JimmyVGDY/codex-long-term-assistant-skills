# V6.2 Native Windows Compatibility Hardening Release

V6.2 builds on V6.1 and incorporates the compatibility issues discovered, fixed, and verified during a real upgrade and lifecycle acceptance run with native Windows Codex CLI 0.150.1. It is not a version-only repackaging.

## Major Changes

- All six Windows Hooks now launch through the quote-free form `cmd.exe /d /c %PLUGIN_ROOT%\hooks\cp_hook.cmd <HookName>`, avoiding Codex 0.150.1 parsing failures for quoted Hook commands.
- `cp_hook.cmd` first looks for the current account's CPython installation, then falls back to `python.exe` or `py.exe -3` on PATH. It neither creates nor requires an extra `python3.exe`.
- Hooks read stdin as raw bytes and write UTF-8 output. A truncated Windows Stop payload containing Chinese text can still recover lifecycle identity fields and return the valid neutral JSON object `{}`.
- Observation-write failures remain fail-open; the PreToolUse model gate remains fail-closed.
- Explicit automatic-subagent models use an exact allowlist containing only `gpt-5.6-luna` and `gpt-5.6-terra`. `xhigh/max/ultra`, Sol, unknown models, and future Terra names are denied.
- The installer uses shorter atomic-staging names and Windows extended-length paths at every backup, copy, verification, uninstall, and rollback I/O boundary. Repeated installation, upgrade backup, and restoration under long account paths no longer depend on the legacy MAX_PATH limit.
- When uninstalling `AGENTS.md` or standalone `hooks.json`, only this package's managed block or exact Hook command is restored. External content added or changed during installation is retained. Malformed existing configuration fails closed and is not overwritten.
- Windows installer tests isolate both `HOME` and `USERPROFILE`. They use a fake `codex.cmd`, long paths, and unprivileged Junctions to verify upgrade restoration and reparse-point protection.
- Natural-language descriptions, rules, Reviewer prompts, and test identities use neutral wording. CLI arguments, JSON fields, path variables, and other machine contracts remain unchanged.

## Unchanged

- 10 engineering Skills, 7 specialist Reviewers, and 6 lifecycle Hooks.
- TaskOutcomeEvent V2, the SHA-256 event chain, and dual project isolation by `project_id + repo_fingerprint`.
- The automatic cost route Luna Low → Luna Medium → Terra Medium → Terra High, with Terra High as the ceiling.
- The main Agent model remains externally selected; Reviewer TOML files do not hard-code models.
- `execution_authorization=NONE`; Proposals are not automatically accepted, executed, or used to modify Skills.
- No automatic commit, push, deployment, restart, production-data write, or production operation.
- Installer dry-run, backup, drift detection, rollback, and protection of unknown external files.

## Compatibility

- Target host: native Windows Codex CLI 0.150.1.
- Supports upgrades from V6.1, V6.0, and older versions declared in the manifest.
- V6.1 project context, Events, Snapshots, Assessments, Proposals, Decisions, and lifecycle records are reused without migration or deletion.
- Plugin success still requires the target entry in `codex plugin list --json` to report `installed=true`, `enabled=true`, and `version=6.2.0`.

## Upgrade Notes

1. Extract the ZIP; do not run the package directly inside the archive.
2. Run `doctor` and the Plugin dry-run.
3. If the dry-run has no blocking issue, perform the account-level Plugin installation.
4. Run `verify` and `codex plugin list --json`.
5. Close and reopen Codex tasks that existed before the upgrade.

See `docs/USER_GUIDE_V6.2.md` for the complete procedure.
