# Codex Cross-Project Engineering Assistant V6.6.1

中文：[README.md](README.md)

Target host: native Windows Codex CLI 0.150.1. Plugin success is established only when `codex plugin list --json` reports `installed=true`, `enabled=true`, and `version=6.6.1`.

Two complete, independently installable, reproducible archives are provided:

- `Codex-Skills-V6.6.1-zh-CN.zip`
- `Codex-Skills-V6.6.1-en.zip`

Both distributions share the same runtime, Hooks, installer, schemas, tests, and safety policy. English primary surfaces cover the README, global rules, ten Skill entry points, seven Reviewer definitions, installation, configuration, operating guidance, and release notes. Historical evidence and low-level fixtures remain preserved in their original form.

## Capabilities

- Ten engineering Skills with progressive routing.
- Seven logically read-only Reviewers with no hard-coded model or reasoning effort.
- Six lifecycle Hooks: `UserPromptSubmit`, `PreToolUse`, `SubagentStart`, `SubagentStop`, `Stop`, and `SessionEnd`.
- TaskOutcomeEvent 2.0 with `project_id + repo_fingerprint` isolation and a continuous hash chain.
- Delayed SessionEnd sealing outside the three-second Hook budget.
- Non-destructive event archives, capacity reporting, and privacy-bounded cross-project health summaries.
- Controlled proposals with `execution_authorization=NONE`.

## Model evidence boundary

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = host diagnostic only
```

Codex 0.150.1 does not provide a trusted, correlatable runtime model attestation to Hooks. A requested Luna or Terra profile is not proof of the model that actually ran. Automatic dispatch follows:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch above `gpt-5.6-terra + high`, including Sol, `xhigh`, `max`, and `ultra`, is rejected.

## Upgrade installation

Run from the extracted language-package root:

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

The dry run must show a bounded backup, contained paths, preserved unknown files, rejected link and reparse risks, and a complete rollback plan. File copying alone is not Plugin success.

Further guidance: `docs/USER_GUIDE_V6.6.1.en.md`, `docs/INSTALLATION_RECOVERY.en.md`, and `docs/CODEX_CONFIG_GUIDE.en.md`.

## Safety boundaries

- No automatic Skill, Reviewer, route, global configuration, or repository modification.
- No automatic proposal acceptance or execution.
- No automatic commit, push, deployment, restart, production operation, or data write.
- Evidence records facts; it never grants authorization.

Licensed under Apache-2.0. See `LICENSE`.
