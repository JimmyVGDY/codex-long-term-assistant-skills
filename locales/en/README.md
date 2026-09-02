<p align="right">
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/README.md">Chinese</a> · <strong>English</strong>
</p>

# Codex Cross-Project Engineering Assistant

<p align="center">
  <img src="docs/assets/social-preview.jpg" alt="Codex bilingual project preview" width="100%">
</p>

<p align="center">
  A cross-project engineering framework for Codex: Skill routing, independent multi-agent review, recoverable task memory, lifecycle events, and controlled evolution.
</p>

<p align="center">
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/github/license/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <img alt="Python 3.8+" src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white">
  <img alt="Codex CLI 0.152.1" src="https://img.shields.io/badge/Codex%20CLI-0.152.1-111827">
</p>

V7.1.0 targets native Windows Codex CLI 0.152.1, adds transactional account-runtime tools and restricted-task fallback, and continues to provide two independently installable, reproducibly built Plugin distributions. The four general primary domains, main-Agent model boundary, and Terra High automatic ceiling remain unchanged.

**Quick links:** [Downloads](#downloads) · [Usage example](#reproducible-usage-example) · [Compatibility](#compatibility-matrix) · [Installation](#five-minute-upgrade) · [Documentation](#documentation-and-collaboration)

## Downloads

| Distribution | Interface | Download |
| --- | --- | --- |
| `Codex-Skills-V7.1.0-zh-CN.zip` | Chinese | [Download zh-CN package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.1.0/Codex-Skills-V7.1.0-zh-CN.zip) |
| `Codex-Skills-V7.1.0-en.zip` | English | [Download English package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.1.0/Codex-Skills-V7.1.0-en.zip) |

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

## Reproducible usage example

The following input, flow, and inspectable outcome show a typical read-only task. This is an illustrative usage example, not runtime evidence for the current session.

**Task input**

```text
Inspect the installer upgrade path in the current repository without modifying files.
Select a Reviewer according to actual risk, and separate confirmed facts, inferences,
and unverified items.
```

**Expected flow**

```text
Task input
  -> route engineering-quality-delivery
  -> read the installer, manifests, tests, and upgrade documentation
  -> start a logically read-only Reviewer when justified by risk
  -> deduplicate and reconcile Reviewer findings
  -> report evidence, risks, and unverified boundaries
```

The lifecycle can produce `TURN_OPENED -> SUBAGENT_STARTED -> SUBAGENT_STOPPED -> TASK_COMPLETED`; `SessionEnd` then enters the delayed sealing path. Model evidence stays separated into three fields:

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = host diagnostic only
```

Here, `requested_model_policy=PASS` only proves that automatic dispatch did not request a configuration above Terra High. It does not attest to the model that actually ran.

## Compatibility matrix

| Environment or mode | Current role | Existing validation level | Boundary |
| --- | --- | --- | --- |
| Native Windows Codex CLI 0.152.1 + Plugin | Primary target | Complete 7.0.0 to 7.1.0 installation, Plugin state, account tools, and payload readback | The public ZIP should still be installed and read back independently in the target account |
| Windows `windows-latest` + Python 3.13 | CI | Bilingual audit, complete-package validation, and release build | CI does not replace acceptance in a real Codex account |
| Ubuntu `ubuntu-latest` + Python 3.13 | CI package compatibility | Bilingual audit and complete-package validation | This is not Linux host acceptance for Plugin, Marketplace, or Hooks |
| standalone mode | Compatibility mode | Installation structure and regression coverage | Not the primary V7.1.0 release-acceptance path |
| macOS | Unverified | No current CI or host-acceptance evidence | Status remains `UNVERIFIED` |

The Python source declares 3.8+ support; public CI currently runs 3.13. For any different environment combination, run `doctor`, `dry-run`, and `verify` before deciding its usable status.

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

3. The upgrade is established only when the Plugin readback reports `installed=true`, `enabled=true`, and `version=7.1.0`, and every legacy Skill directory declared by the Manifest is absent.

The installer detects an existing version, creates a bounded backup, rejects link and reparse-point risks, preserves unknown files, and removes only Manifest-declared legacy Skill directories: the three V7 domain replacements plus the previously deprecated Vue Skill. See [Installation and recovery](docs/INSTALLATION_RECOVERY.md) and the [User guide](docs/USER_GUIDE_V7.1.md).

## Model evidence boundary

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = host diagnostic only
```

Codex 0.152.1 does not provide Hooks with a trusted, correlatable runtime model attestation. A requested Luna or Terra profile is not proof of the model that actually ran. The automatic cost ladder is:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch rejects Sol, `xhigh`, `max`, `ultra`, and every configuration above `gpt-5.6-terra + high`.

## Documentation and collaboration

- [Documentation hub](docs/README.md): installation, configuration, architecture, model policy, validation, and history.
- [Contributing guide](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/CONTRIBUTING.en.md): branches, commits, bilingual coverage, and validation.
- [Security policy](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/SECURITY.en.md): vulnerability reporting and sensitive-information handling.
- [Code of conduct](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/CODE_OF_CONDUCT.en.md): baseline boundaries for public collaboration.
- [Changelog](CHANGELOG.md) · [V7.1.0 release notes](docs/releases/v7.1.0/RELEASE_NOTES.md)

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
