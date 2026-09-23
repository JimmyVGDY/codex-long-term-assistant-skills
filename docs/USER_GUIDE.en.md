<!-- Generated from locales/en/docs/USER_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.0 Operating Guide

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/USER_GUIDE/)

## Quick start

From the extracted V7.12.0 package, run `./scripts/install-base.ps1` on Windows or `./scripts/install-base.sh` on POSIX, then describe your engineering task. The base Plugin loads ten Skills without the package Python runtime or an API key. It does not install account Hooks, Reviewers, global rules, or long-term runtime state.

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

The [capability index](CAPABILITY_INDEX.en.md) links the complete commands. The dispatch budget below is a separate task-scoped opt-in control.

## 1. Dispatch budget and privacy

Reviewer, Explorer, and Worker share one root budget; the review controller never charges twice. New tasks use Budget V3, Reviewer state V8, and result V5; old tasks pin their original policy. The main agent retains its current selection. Workers/Explorers keep the original four combinations. Registered Reviewers start at Luna Low with one point, add review-budget and valid-evidence points, then select one of ten combinations for one dispatch, capped at Astra High.

Proxy units are neither actual prices nor a capability ranking. See [model selection and budget](../locales/en/docs/MODEL_ROUTING_AND_COST_POLICY.md) for combinations, evidence deduplication, quality constraints, extensions, and family limits. Stop when no acceptable combination is affordable.

## 2. Workflow

1. Bind an external Project Profile, initialize a Task Envelope with the new scoring policy, and choose LIGHT, STANDARD, or STRICT.
2. Initialize the external V3 ledger with `--root-envelope` and the genuine host session binding. Old tasks explicitly select `--policy-id four-tier-v1`; an old envelope cannot silently become a new-policy task.
3. Decide INLINE or DELEGATE first. Reviewer `decide` takes `--selection-input`, `--review-assignment`, and the root envelope. Supply evidence references and paths, never submitted totals. The program scores from Luna and freezes the final combination and permit.
4. Bind that permit, packet hash, and unique review slot in the V8 controller. Dispatch once using either its named parameters or `native_request_parameters` for the host interface. Native calls without task names must prepend the returned `native_message_prefix` verbatim to `message`. Missing, incorrect, or consumed references reject; roles never select permits implicitly. Reviewer combinations must be explicit.
5. Launch the host with `CP_DELEGATION_BUDGET_PATH`, `CP_DELEGATION_ENVELOPE_PATH`, and `CP_DELEGATION_BUDGET_REQUIRED=1`. PreToolUse verifies the genuine root identity, current baseline, role, and permit before atomic reservation.
6. Join the exact PostToolUse tool-call/agent-ID receipt to SubagentStart/Stop, including out-of-order callbacks. V3 start/complete CLI calls cannot replace native receipts. Missing association, timeout, or unknown responses remain incomplete and cannot imply PASS or refunds.

The enhancement does not automatically create task ledgers. Unactivated tasks are policy-only; missing or corrupt required budget configuration denies dispatch. Automatic no-start refunds remain unavailable until a native no-create response contract is verified. Started, failed, or cancelled work is not refunded.

## 3. Retries and transitions

Missing evidence is not an upgrade reason. Same-family effort increases and cross-family switches have separate records. Re-review binds the prior terminal attempt, result references, and new evidence; renaming cannot reuse permits or reset counts. Retries require an explicit new round or slot within the same root budget.

## 4. Cost and calibration

Store only approved combinations, scoring, and cost proxies; never read, infer, or store underlying host model identity. Samples pin project, repository, policy digest, formula, and declared comparison pair. Old units never mix with a new formula. Parent finalization with result and validation references precedes replay; insufficient samples retain NO_CHANGE. Proposals permanently retain `execution_authorization=NONE`.

Budget V1 is read-only; V2 preserves original byte-level replay and continuation. V7/V4 reviews keep their old semantics. New tasks use separate V3 ledgers; unknown versions fail closed. Installation, registration, Hook behavior, native dispatch, and underlying identity are distinct evidence layers. Synthetic tests never replace host acceptance.

## 5. Codex 0.154.0 scope

V7.12.0 supports Codex CLI 0.154.0 and the ten preceding stable releases exactly as frozen in `config/codex-compatibility-v1.json`. Upstream 0.154.0 fixes Astra visibility in the bundled model picker, makes Astra the bundled default when no model is explicitly configured, and limits async-question guidance to sessions where the tool is available. These changes do not alter the frozen Plugin/Hook contract. Workers and Explorers retain the original four Luna/Terra combinations; registered Reviewers start from Luna, score evidence and budget, and are capped at Astra High. The local Marketplace manifest requires `interface.displayName`; future, prerelease, and other out-of-window hosts are not admitted automatically.

Base installation requires Plugin readback of `installed=true`, `enabled=true`, and `version=7.12.0`, ten Skills, and no Plugin Hooks. Enhancement installation additionally requires a `HOST_COMPATIBLE` schema-3 snapshot and verification of account Hooks and managed runtime assets.

## Feedback and measured benefits

V7.9 retains the validation feedback introduced in V7.5, health gates, opt-in incremental analysis, per-ledger scenario calibration, testable hypotheses, and verified benefit closure. V7.6.2 no longer injects a binding from asynchronous UserPromptSubmit; identity is supplied explicitly by the current repository-external execution envelope. Follow the [controlled evolution operations manual](../locales/en/docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md). Automation remains disabled until explicitly enabled for the project.

## Capability reuse and optional gates

Use the [capability index](CAPABILITY_INDEX.en.md) for bounded initial scans and incremental updates. Recheck candidate source, semantic compatibility, and maintenance cost before reuse. Project gates are disabled by default. With an explicitly enabled policy, V7.12.0 routes canonical `apply_patch` through Operation v2: A creates an origin and is denied, a different B claims permission after preparation, and only B's matching PostToolUse receipt can complete verification. Legacy GateTask never becomes a new permit. See the [acceptance protocol](COMPONENT_REUSE_ACCEPTANCE.en.md) and [release validation](releases/v7.12.0/VALIDATION_REPORT.en.md).
