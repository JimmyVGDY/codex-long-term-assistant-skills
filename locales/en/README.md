# Codex Cross-Project Engineering Assistant V6.6.1

Target host: native Windows Codex CLI 0.150.1. Plugin success is established only when `codex plugin list --json` reports `installed=true`, `enabled=true`, and `version=6.6.1`.

This English distribution is a complete installable archive. It shares the same runtime, Hooks, installer, schemas, tests, and safety policy with the zh-CN distribution. English primary surfaces cover this README, installation and configuration guidance, the global rules, ten Skill entry points, seven Reviewer definitions, and release notes. Historical evidence and low-level fixtures remain preserved in their original form.

## Capabilities

- Ten engineering Skills with minimal routing.
- Seven logically read-only Reviewers with no hard-coded model.
- Six lifecycle Hooks: `UserPromptSubmit`, `PreToolUse`, `SubagentStart`, `SubagentStop`, `Stop`, and `SessionEnd`.
- TaskOutcomeEvent schema 2.0 with `project_id + repo_fingerprint` isolation and a hash chain.
- Delayed SessionEnd sealing outside the three-second Hook budget.
- Non-destructive event archives, capacity reporting, and privacy-bounded health summaries.
- Controlled proposals with `execution_authorization=NONE`.

## Model evidence boundary

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = host diagnostic only
```

Codex 0.150.1 does not provide a trusted, correlatable runtime model attestation to Hooks. A requested Luna or Terra profile is not proof of the model that actually ran. Automatic dispatch may request only:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch above `gpt-5.6-terra + high`, including Sol, `xhigh`, `max`, and `ultra`, is rejected.

## Upgrade installation

Run from the extracted package root:

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

The dry run must show a bounded backup, contained paths, preserved unknown files, and a complete rollback plan. File copying alone is not Plugin success. Existing project context, events, snapshots, and proposals remain preserved.

Further guidance: `docs/USER_GUIDE_V6.6.1.md`, `docs/INSTALLATION_RECOVERY.md`, and `docs/CODEX_CONFIG_GUIDE.md`.

## Safety boundaries

- No automatic Skill, Reviewer, route, global configuration, or repository modification.
- No automatic proposal acceptance or execution.
- No automatic commit, push, deployment, restart, production operation, or data write.
- Evidence records facts; it never grants authorization.

Licensed under Apache-2.0. See `LICENSE`.
