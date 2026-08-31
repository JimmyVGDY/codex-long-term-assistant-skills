# Codex Cross-Project Engineering Assistant

<p align="center">
  A cross-project engineering framework for Codex: Skill routing, independent multi-agent review, recoverable task memory, lifecycle events, and controlled evolution.
</p>

<p align="center">
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/github/license/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <img alt="Python 3.8+" src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white">
  <img alt="Codex CLI 0.150.1" src="https://img.shields.io/badge/Codex%20CLI-0.150.1-111827">
</p>

<p align="center">
  <a href="README.md">Chinese</a> · <strong>English</strong>
</p>

V6.6.1 targets native Windows Codex CLI 0.150.1 and provides two independently installable, reproducibly built Plugin distributions. The main Agent model configuration remains untouched, while Terra High is the maximum automatic sub-agent policy tier.

## Downloads

| Distribution | Interface | Download |
| --- | --- | --- |
| `Codex-Skills-V6.6.1-zh-CN.zip` | Chinese | [Download zh-CN package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v6.6.1/Codex-Skills-V6.6.1-zh-CN.zip) |
| `Codex-Skills-V6.6.1-en.zip` | English | [Download English package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v6.6.1/Codex-Skills-V6.6.1-en.zip) |

[Open the latest Release, checksums, and build witnesses](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest)

## Core capabilities

- Ten engineering Skills with minimal, progressive routing for the active task.
- Seven logically read-only Reviewers with no hard-coded model or reasoning effort.
- Six lifecycle Hooks: `UserPromptSubmit`, `PreToolUse`, `SubagentStart`, `SubagentStop`, `Stop`, and `SessionEnd`.
- TaskOutcomeEvent 2.0 with `project_id + repo_fingerprint` isolation and a continuous hash chain.
- Recoverable checkpoints, delayed SessionEnd sealing, event archives, and cross-project health summaries.
- Controlled proposals fixed at `execution_authorization=NONE`, without implementation authority.

```mermaid
flowchart LR
    A[Task input] --> B[Minimal Skill routing]
    B --> C[Main Agent execution]
    C --> D[Independent Reviewers]
    C --> E[Lifecycle Hooks]
    D --> E
    E --> F[TaskOutcomeEvent 2.0]
    F --> G[Project isolation and hash chain]
    G --> H[Snapshot / Assessment / Proposal]
    H --> I[Human decision]
```

## Five-minute upgrade

1. Download one language archive and extract it into a temporary directory.
2. Run the following commands from the extracted package root:

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

3. The upgrade is established only when the Plugin readback reports `installed=true`, `enabled=true`, and `version=6.6.1`.

The installer detects an existing version, creates a bounded backup, rejects link and reparse-point risks, and preserves unknown files. See [Installation and recovery](docs/INSTALLATION_RECOVERY.en.md) and the [User guide](docs/USER_GUIDE_V6.6.1.en.md).

## Model evidence boundary

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = host diagnostic only
```

Codex 0.150.1 does not provide Hooks with a trusted, correlatable runtime model attestation. A requested Luna or Terra profile is not proof of the model that actually ran. The automatic cost ladder is:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch rejects Sol, `xhigh`, `max`, `ultra`, and every configuration above `gpt-5.6-terra + high`.

## Documentation and collaboration

- [Documentation hub](docs/README.en.md): installation, configuration, architecture, model policy, validation, and history.
- [Contributing guide](.github/CONTRIBUTING.en.md): branches, commits, bilingual coverage, and validation.
- [Security policy](.github/SECURITY.en.md): vulnerability reporting and sensitive-information handling.
- [Code of conduct](.github/CODE_OF_CONDUCT.en.md): baseline boundaries for public collaboration.
- [Changelog](CHANGELOG.en.md) · [V6.6.1 release notes](docs/releases/v6.6.1/RELEASE_NOTES.en.md)

## Local validation

```powershell
python scripts\localization-audit.py --strict
python scripts\validate-package.py
```

Release builds use fixed timestamps, stable ordering, and SHA-256 witnesses. The source repository and release archive are separate evidence layers: repository CI validates a commit, while Release assets and witnesses validate downloadable artifacts.

## Safety boundaries

- No automatic Skill, Reviewer, model-route, global-configuration, or business-repository modification.
- No automatic proposal acceptance or execution.
- No automatic commit, push, deployment, restart, production operation, or business-data write.
- Evidence records facts and never grants authority.
- Raw prompts, complete responses, source bodies, diffs, tokens, cookies, API keys, and credentials are not stored by default.

Licensed under Apache-2.0. See [LICENSE](LICENSE).
