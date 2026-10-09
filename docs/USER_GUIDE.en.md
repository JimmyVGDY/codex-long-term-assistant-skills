<!-- Generated from locales/en/docs/USER_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

# V7.15.2 Operating Guide

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/USER_GUIDE/)

## Quick start

From the extracted V7.15.2 package, run `./scripts/install-base.ps1` on Windows or `./scripts/install-base.sh` on POSIX, then describe your engineering task. The base Plugin loads ten Skills without the package Python runtime or an API key. It does not install account Hooks, Reviewers, global rules, or long-term runtime state.

Simple local tasks run with the main Agent by default. A Profile, index, full scan, and budget ledger are not prerequisites. Add the optional enhancement through `install-user` only when needed; see [installation and recovery](operations/INSTALLATION_RECOVERY.en.md). The index, Hook, and budget procedures below apply to that enhancement. Strict budgeting requires a verifiable host binding, ledger, and dispatch permit; otherwise the model ceiling remains a policy constraint.

## Four daily paths and the unified entry

New users can start from four paths: fix a bug, build a feature, review, or continue a task. The extracted package provides `scripts/cp-assistant.ps1`, `scripts/cp-assistant.sh`, and `scripts/cp-assistant.py`. They use a whitelist to forward to the existing installer and runtime; the legacy `package_manager.py`, `cp-runtime.py`, and base launchers remain available.

| Path | Example request | Boundary |
| --- | --- | --- |
| Fix a bug | “Fix the failing validation and run the smallest relevant test.” | Let the Agent read the current code and focused tests; no enhancement is required first. |
| Build a feature | “Implement this feature and validate it according to risk.” | Add enhancements only when long-running state, Hooks, Reviewers, budgets, or controlled writes are needed. |
| Review | “Review this branch for compatibility, security, and rollback risks.” | A Reviewer is risk- and evidence-driven; the entry does not force one. |
| Continue a task | “Continue the previous task and tell me where it stopped and what is next.” | Use read-only `resume` for the stage, checkpoint, repository changes, and evidence needing revalidation. |

Unified-entry examples:

```powershell
.\scripts\cp-assistant.ps1 help
.\scripts\cp-assistant.ps1 install-base
.\scripts\cp-assistant.ps1 status
.\scripts\cp-assistant.ps1 doctor
.\scripts\cp-assistant.ps1 inventory --scope user --mode plugin --json
.\scripts\cp-assistant.ps1 resume --repo-path E:\work\repo --profile C:\safe-state\project-profile.json --checkpoint-dir C:\safe-state\task
.\scripts\cp-assistant.ps1 recover --scope user
```

`status`, `doctor`, `inventory`, `verify`, and `resume` are query or verification actions. `install-base`, `install-enhancement`, and `recover` change managed state. Queries do not install, initialize a Profile, refresh an index, repair a ledger, or invoke installation recovery. `resume` supports a bound `--profile` (optionally with `--state` and repeated `--evidence`) or an explicitly supplied `--checkpoint-dir` for legacy Markdown checkpoints. Missing input, stale evidence, budget exhaustion, and repository changes remain `UNKNOWN/PARTIAL/STALE`; the command never fabricates a current pass.

The unified entry only promises parameters that exist. `verify` does not accept the nonexistent `--json`; use `status --json`, `doctor --json`, `inventory --json`, or `resume --json` for machine JSON. Without Python, `help` and `install-base` still work. Other management commands return an explicit dependency-missing structure and point to `codex plugin list --json` for native readback.

## Experience benchmark

`scripts/ux-benchmark.py` runs deterministic command samples only when explicitly invoked. It does not start a model, upload data, or save prompts or complete outputs. The `collect`, `import-observations`, and `compare` protocol and privacy fields are documented in `tests/fixtures/ux-benchmark/protocol.json`. Wrapper-layer duration or tool-count changes describe the measured samples only; they do not by themselves prove a real Agent-task speedup.

`status` and `doctor` accept `--profile <project-Profile> --repo-path <repository>` to inspect explicit project control prerequisites. Enabled controls with an unavailable runtime block the affected capability; without an actual operation permit, diagnostics do not assert that a controlled write can execute. `inventory` reports unreadable files or corrupt state without repairing or deleting assets.

Benchmark collection accepts `--command-file <JSON-argument-array-file>` to avoid shell quoting issues. Outputs must be new files outside the package root. Comparisons recompute statistics and require a full source SHA plus matching fixture, scenario, and environment. Fewer than 20 valid timings produce no p95.

## Component reuse workflow

1. Verify the repository, Project Profile, existing external index, and coverage. The index locates evidence; source and contracts decide suitability.
2. Bound the initial scan to relevant public capabilities. Record unfinished coverage when limits are reached. Later tasks query candidates before reading source, callers, and tests.
3. Compare semantics, authorization, contracts, state, dependencies, resources, tests/rollback, and maintenance cost; choose reuse, extend, extract, or independent implementation.
4. Enable the optional gate explicitly and read back status. In a new task with actually loaded Hooks, run prepare, development/validation, finish, and check. Enablement alone neither creates an index nor proves execution.
5. Refresh changed source and adopted stale candidates only. Register new public capabilities and preserve IDs during migration. Unrelated or unchanged work does not cause repeated scans.
6. Preserve PARTIAL, BLOCKED, FAILED, and CANCELLED outcomes. Disabling retains the index and receipts. Workflow PASS never replaces semantic and compatibility validation.

The [capability index](CAPABILITY_INDEX.en.md) links the complete commands. The enhanced runtime manages the root budget below; the base Plugin does not establish enforced accounting.

## 1. Dispatch budget and privacy

Reviewers, Explorers and Workers share one root budget. New enhanced-runtime tasks use `desktop-g6-deterministic-v1` and the nine GPT-6 profiles, defaulting unknown work to Sol/medium without statistical qualification. Keep the main agent's selection and old roots' original policy and charges.

Scripts compute facts, selection, reservations, required holds and retries. Models retain semantic judgment and bounded proposals, then execute approved parameters. Planning units are not actual fees or capability rankings; see [model selection and budget](../locales/en/docs/MODEL_ROUTING_AND_COST_POLICY.md). Missing evidence uses default/degraded continuation; budget limits allow queuing, scoped alternatives or local work without invented calls.

## 2. Workflow

1. Identify the project, task and bound policy. New tasks use an authorized default template; old roots replay unchanged. Handoff preserves charges and late-event ownership.
2. Read the default tuple, allowed adjustments, budget, gate states and next action from the enhanced runtime preparation entry. Unknown facts stay UNKNOWN.
3. Execute exact script parameters. Submit structured reading, splitting, ordering or profile adjustments for recalculation. Missing lengthy rationale or gain cards does not stop default work.
4. PreToolUse atomically reserves resources. Link actual receipts and child terminal events by identity; generic status, timeout or a cancellation request cannot imply PASS or refunds.
5. Parent/child tools, pre-review, post-review, repair and installation use consistent missing-evidence rules. Continue reversible work while confirmed violations restrict their affected action. Platform permission and trust controls remain enabled.
6. A base Plugin that loads Skills alone does not establish the enhanced journal or Hook guarantees; use actual installation readback. Report genuinely unavailable interfaces and continue feasible local work.

## 3. Retries and transitions

Classify retries and bound them by the root budget and total time. Resume the same handle while running or uncertain. Do not repeat unchanged material without new information. Necessary downgrades do not consume upward-adjustment slots; policy changes and splitting do not reset the budget. Explicit user model choices take precedence; report real capability or budget conflicts.

## 4. Cost and calibration

Keep approved tuples, planning units and available actual metering separate. Semantic advice is not verified fact. Naturally occurring independent samples may inform a later policy version; insufficient samples retain current parameters without stopping default service or restoring qualification prerequisites. Proposals always retain `execution_authorization=NONE`.

Read V1/V2/V3/V4 ledgers and results under their frozen contracts without repricing or regrading. Installation, registration, Hooks, native dispatch, validation and effective state are separate readbacks. Synthetic tests cannot replace native Desktop acceptance.

## 5. Codex 0.160.1 scope

V7.14.6 freezes an internal component window covering Codex CLI 0.160.1 and the ten preceding stable releases in `config/codex-compatibility-v1.json`; this does not establish standalone CLI product support. The local Marketplace manifest requires `interface.displayName`, and future, prerelease, or out-of-window hosts are not admitted automatically. Version 0.160.1 backports Windows remote stdio MCP environment preservation so explicitly configured remote environments retain `SYSTEMROOT`, `TEMP`, and `TMP`; this does not alter this package's reviewer qualification, model defaults, or Operation v2 contract. The 0.160.0 workspace, queue-recovery, and Windows-fix evidence remains retained. Hook discovery/schema and apply_patch handler/context contracts did not drift, so active `0.160.x`, `0.159.x`, and 0.158.0 releases reuse `result-v158`; 0.155.0 has left the window and remains fail-closed, while 0.155.1 still uses `result-v155`. This V7.14.6 component baseline does not define the new model default. New tasks use the GPT-6 policy above; qualification prerequisites belong only to explicit legacy contracts.

Base installation requires Plugin readback of `installed=true`, `enabled=true`, and `version=7.15.2`, ten Skills, and no Plugin Hooks. Enhancement installation additionally requires a `HOST_COMPATIBLE` schema-3 snapshot and verification of account Hooks and managed runtime assets.

## Feedback and measured benefits

V7.9 retains the validation feedback introduced in V7.5, health gates, opt-in incremental analysis, per-ledger scenario calibration, testable hypotheses, and verified benefit closure. V7.6.2 no longer injects a binding from asynchronous UserPromptSubmit; identity is supplied explicitly by the current repository-external execution envelope. Follow the [controlled evolution operations manual](../locales/en/docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md). Automation remains disabled until explicitly enabled for the project.

## Capability reuse and optional gates

Use the [capability index](CAPABILITY_INDEX.en.md) for bounded initial scans and incremental updates. Recheck candidate source, semantic compatibility, and maintenance cost before reuse. Project gates are disabled by default. With an explicitly enabled policy, V7.14.6 routes canonical `apply_patch` through Operation v2: A creates an origin and is denied, a different B claims permission after preparation, and only B's matching PostToolUse receipt can complete verification. Legacy GateTask never becomes a new permit. See the [acceptance protocol](COMPONENT_REUSE_ACCEPTANCE.en.md) and [release validation](releases/v7.14.6/VALIDATION_REPORT.en.md).
