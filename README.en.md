<!-- Generated from locales/en/README.md; edit that source and run scripts/documentation.py sync. -->

<p align="right">
  <a href="https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/">Chinese</a> · <strong>English</strong>
</p>

V7.9.0 provides ready-to-use base installation with optional enhancement runtime. Ordinary engineering work can begin directly, while Hooks, recoverable state, budgets, and controlled writes attach only when needed.

# Codex Cross-Project Engineering Assistant

<p align="center">
  <img src="docs/assets/social-preview.jpg" alt="Codex bilingual project preview" width="100%">
</p>

<p align="center">
  A cross-project engineering framework for Codex: Skill routing, independent multi-agent review, recoverable task memory, lifecycle events, and controlled evolution.
</p>

<p align="center">
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://jimmyvgdy.github.io/codex-long-term-assistant-skills/"><img alt="Bilingual documentation" src="https://img.shields.io/badge/docs-%E4%B8%AD%E6%96%87%20%7C%20English-00b8a9"></a>
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/github/license/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Codex CLI 0.154.0" src="https://img.shields.io/badge/Codex%20CLI-0.154.0-111827">
</p>

V7.6.2 restored the non-blocking message and Stop boundary; V7.7.0 added Operation v2; and V7.7.1 moved the compatibility window to Codex CLI 0.154.0. V7.9.0 retains those safety boundaries while separating base Skills from optional enhancement runtime. The gate remains off by default, and capability level is neither semantic correctness nor authority.

**Quick links:** [Bilingual documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/) · [Downloads](#downloads) · [Start](#start-in-two-steps) · [Compatibility](#compatibility-matrix) · [Upgrade](#first-install-and-upgrade) · [Documentation](#documentation-and-collaboration)

Use the assistant directly after installation; ordinary work does not require learning Profiles, indexes, or ledgers first. The first full scan is optional. Declining it, leaving it unanswered, or losing auxiliary storage keeps the current-source BASIC path available. For recovery, use `doctor`, read-only `inventory`, and canonical `recover` in that order; each reports the affected feature, what still works, and the next action.

## Start in two steps

1. Extract the package and install the base Plugin with its native launcher. This does not need this package's Python runtime or an API key.

   ```powershell
   .\scripts\install-base.ps1
   ```

   ```sh
   ./scripts/install-base.sh
   ```

2. Describe the work in ordinary language. For example:

   ```text
   Fix the failing validation in this repository and run the smallest relevant test.
   Review the changes I made in this branch for compatibility and security risks.
   Continue the previous task; first confirm what is already changed and what still needs verification.
   ```

The base Plugin loads the ten Skills once and does not start Hooks, workers, Profile creation, indexing, or a budget ledger. Those remain optional enhancements rather than prerequisites for ordinary work.

## Optional enhancements

Use the existing enhanced installer only when the task needs recoverable long-running state, Hooks, indexing, an independent Reviewer, an enforced budget, or controlled writes. It performs the existing backup, transaction, verification, and recovery steps; a managed enhancement installation is never downgraded by the base launcher.

## Downloads

| Distribution | Interface | Download |
| --- | --- | --- |
| `Codex-Skills-V7.9.0-zh-CN.zip` | Chinese | [Download zh-CN package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.9.0/Codex-Skills-V7.9.0-zh-CN.zip) |
| `Codex-Skills-V7.9.0-en.zip` | English | [Download English package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.9.0/Codex-Skills-V7.9.0-en.zip) |

[Open the latest Release, checksums, and build witnesses](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest)

## Core capabilities

- Ten engineering Skills with minimal, progressive routing for the active task.
- The C01-C25 registry defaults to AUTO/BASIC. A missing prerequisite degrades only that capability, while explicit OFF and task risk are evaluated separately.
- A first full scan queues only after an explicit persisted choice. Decline, no reply, cancellation, persistence failure, and late workers have separate states.
- Seven logically read-only Reviewers with no hard-coded model or reasoning effort.
- The enhanced installation registers <!-- cp-fact:hooks.en -->8 registered Hook entry points: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SubagentStart`, `SubagentStop`, `Stop`, `Interrupt`, `SessionEnd`.<!-- /cp-fact --> The base Plugin registers none; enhanced UserPromptSubmit is asynchronous observation, Stop is neutral, and Interrupt remains host-controlled.
- TaskOutcomeEvent 3.0 with `project_id + repo_fingerprint` isolation and a separate continuous hash chain.
- Recoverable checkpoints, delayed SessionEnd sealing, event archives, and cross-project health summaries.
- Separate package routing regression from real-host routing acceptance, binding host evidence to raw final-report SHA-256 digests.
- Evaluate evidence sufficiency per evolution signal instead of globally blocking on unrelated missing telemetry.
- Controlled proposals fixed at `execution_authorization=NONE`, without implementation authority.

```mermaid
flowchart LR
    A[Task input] --> B[Minimal Skill routing]
    B --> C[Main Agent execution]
    C --> D[Independent Reviewers]
    C --> E[Lifecycle Hooks]
    D --> E
    E --> F[TaskOutcomeEvent 3.0]
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
dispatch_policy_status = PASS
host_model_identity = NOT_COLLECTED
```

Here, `requested_model_policy=PASS` only proves that automatic dispatch did not request a configuration above Terra High. It does not attest to the model that actually ran.

## Compatibility matrix

| Environment or mode | Current role | Existing validation level | Boundary |
| --- | --- | --- | --- |
| Native Windows Codex CLI 0.154.0 + Plugin | Current real-host anchor | V7.9.0 account installation, `verify`, and a projectless fresh CLI task passed | A restarted Desktop session remains unverified |
| Windows + eleven pinned stable Codex releases | Frozen compatibility window | The registry binds 11/11 official async, Pre/Post schema, and result-response source evidence | The cross-version real-host matrix has not been run on every host |
| Windows / Ubuntu GitHub matrix | Release gate | The workflow is configured for Python 3.11/3.13 and eleven-version replay on both systems | Refer to GitHub Actions for this release's remote CI state |
| standalone mode | Explicit fallback | Local installation structure, inventory, non-Git BASIC, and regression coverage | It is not a substitute for this account Plugin acceptance |
| macOS | Unverified | No current CI or host-acceptance evidence | Status remains `UNVERIFIED` |

The minimum Python version is 3.11; public CI is configured to validate both 3.11 and 3.13 on Windows and Ubuntu. For any other environment combination, run `doctor`, `dry-run`, and `verify` before deciding its usable status.

The V7.9.0 window is `0.154.0`, `0.153.4`, `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, `0.151.0`, `0.150.1`, and `0.150.0`. Patch releases count independently; future, prerelease, and other out-of-window hosts are not admitted automatically.

## First install and upgrade

For a new installation, use the base launcher above. To add enhancements, or to upgrade an existing managed V7 installation, run the following commands from the extracted package root:

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

The enhanced installation is established only when Plugin readback reports `installed=true`, `enabled=true`, the expected release version, a compatible host snapshot, and no declared legacy Skill directory. `doctor` and `status` normally show what remains usable, what is affected, why, and the one next action; use `--json` for the full machine-readable record.

The installer detects an existing version, creates a bounded backup, rejects link and reparse-point risks, preserves unknown files, and removes only Manifest-declared legacy Skill directories: the three V7 domain replacements plus the previously deprecated Vue Skill. See [Installation and recovery](docs/operations/INSTALLATION_RECOVERY.en.md) and the [User guide](docs/USER_GUIDE.en.md).

## Model evidence boundary

```ini
dispatch_policy_status = PASS
host_model_identity = NOT_COLLECTED
```

Ordinary Hook payloads do not provide a trusted, correlatable runtime-model attestation. A requested Luna or Terra profile is not proof of the model that actually ran. The automatic cost ladder is:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch rejects Sol, `xhigh`, `max`, `ultra`, and every configuration above `gpt-5.6-terra + high`.

## Documentation and collaboration

- [Documentation hub](docs/README.en.md): installation, configuration, architecture, model policy, validation, and history.
- [Contributing guide](.github/CONTRIBUTING.en.md): branches, commits, bilingual coverage, and validation.
- [Security policy](.github/SECURITY.en.md): vulnerability reporting and sensitive-information handling.
- [Code of conduct](.github/CODE_OF_CONDUCT.en.md): baseline boundaries for public collaboration.
- [Changelog](CHANGELOG.en.md) · [V7.9.0 release notes](locales/en/docs/releases/v7.9.0/RELEASE_NOTES.md)

## Local validation

```powershell
python scripts\localization-audit.py --strict
python scripts\validate-package.py
```

Release builds use fixed timestamps, stable ordering, and SHA-256 witnesses. The source repository and release archive are separate evidence layers: repository CI validates a commit, while Release assets and witnesses validate downloadable artifacts.

## Release provenance

The `Release Candidate and Provenance` workflow validates version tags, checks the source on Windows and Ubuntu, builds both reproducible ZIP files, and uses GitHub Artifact Attestations to generate signed provenance for the actual ZIP digests. An authorized public Release is created and read back separately.

```shell
gh attestation verify Codex-Skills-V7.9.0-en.zip --repo OWNER/REPOSITORY
```

See [Release automation and artifact provenance](docs/releases/RELEASE_AUTOMATION.en.md) for the complete gates and new-version procedure.

## Safety boundaries

- No automatic Skill, Reviewer, model-route, global-configuration, or business-repository modification.
- No automatic proposal acceptance or execution.
- No automatic commit, push, deployment, restart, production operation, or business-data write.
- Evidence records facts and never grants authority.
- Raw prompts, complete responses, source bodies, diffs, tokens, cookies, API keys, and credentials are not stored by default.

Licensed under Apache-2.0. See [LICENSE](LICENSE).

Reuse guidance: [Capability index](docs/CAPABILITY_INDEX.en.md) · [Acceptance protocol](docs/COMPONENT_REUSE_ACCEPTANCE.en.md).

V7.6.0 post-release readback (checked at 2026-09-09 04:04:02 UTC): the [release workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304636222), [main-branch CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304540318), and [documentation deployment](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304540320) passed for commit `26d013fa824fa148a839d30aaedd22f3744e8bbf`. This record belongs to that tag and verification time, not subsequent changes, and does not establish cancellation support on every host.
