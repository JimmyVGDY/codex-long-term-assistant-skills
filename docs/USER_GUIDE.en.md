<!-- Generated from locales/en/docs/USER_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

# V7.7 Operating Guide

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/USER_GUIDE_V7.6/)

## Component reuse workflow

1. Verify the repository, Project Profile, existing external index, and coverage. The index locates evidence; source and contracts decide suitability.
2. Bound the initial scan to relevant public capabilities. Record unfinished coverage when limits are reached. Later tasks query candidates before reading source, callers, and tests.
3. Compare semantics, authorization, contracts, state, dependencies, resources, tests/rollback, and maintenance cost; choose reuse, extend, extract, or independent implementation.
4. Enable the optional gate explicitly and read back status. In a new task with actually loaded Hooks, run prepare, development/validation, finish, and check. Enablement alone neither creates an index nor proves execution.
5. Refresh changed source and adopted stale candidates only. Register new public capabilities and preserve IDs during migration. Unrelated or unchanged work does not cause repeated scans.
6. Preserve PARTIAL, BLOCKED, FAILED, and CANCELLED outcomes. Disabling retains the index and receipts. Workflow PASS never replaces semantic and compatibility validation.

The [capability index](CAPABILITY_INDEX.en.md) links the complete commands. The dispatch budget below is a separate task-scoped opt-in control.

## 1. Dispatch budget and privacy

V7.6.2 preserves one root-task weighted budget for Reviewer, Explorer, and Worker while tightening model-identity privacy to the pre-dispatch boundary. The Task Envelope declares the class, `delegation-budget.py` owns the repository-external append-only Budget V2 ledger, the PreToolUse Hook reserves the approved profile atomically before dispatch, and the Reviewer controller keeps rounds and findings without charging twice or receiving host runtime model identity.

Weights are fixed at `luna-low=1`, `luna-medium=2`, `terra-medium=4`, and `terra-high=8`.

| Class | Units | Dispatches | Parallel | Depth | Terra High |
|---|---:|---:|---:|---:|---:|
| LIGHT | 4 | 2 | 1 | 1 | 0 |
| STANDARD | 16 | 6 | 3 | 2 | 1 |
| STRICT | 32 | 10 | 3 | 2 | 1 |

## 2. Workflow

1. Initialize the Task Envelope and choose a budget class.
2. Initialize DelegationBudget V2 outside the repository.
3. Record an `INLINE` or `DELEGATE` decision before every dispatch. A delegated call needs a controlled reason and an opaque unique dispatch key; exact model requests may exist only transiently during host-adapter validation.
4. In the Codex host launch environment, point `CP_DELEGATION_BUDGET_PATH` at the ledger and also set `CP_DELEGATION_BUDGET_REQUIRED=1`. PreToolUse permits the call only when the stable host dispatch ID, role, approved profile, and permit agree; required mode fails closed when the ledger path is missing.
5. Start/Stop reconciliation occurs only when the host propagates `reservation_id`. Codex 0.153.2 omits it in the observed path, so the reservation remains `RESERVED`; time-order guessing is forbidden.
6. Only host proof that an agent did not start can release a reservation. A started agent is never refunded.

V7.6.2 does not create a root-task ledger automatically. The unified budget is activated explicitly per task. Without both environment variables, the Hook still enforces the automatic dispatch-profile ceiling, but that task must not be reported as having passed the unified budget gate.

## 3. Routing contract

Allowed reasons are `INDEPENDENT_EVIDENCE_GAIN`, `SEMANTIC_COMPLEXITY`, `EVIDENCE_CONFLICT`, `SECURITY_OR_CONCURRENCY_RISK`, `LOWER_TIER_INCONCLUSIVE`, `MISSING_EVIDENCE`, and `INLINE_SUFFICIENT`.

Missing evidence cannot justify an upgrade. Inconclusive lower-tier work must reference the preceding tier and may advance only one step. Terra High requires a security/concurrency risk or a referenced stepwise escalation. Unknown roles and invalid inputs fail closed.

## 4. Approved profile, cost, and calibration

An omitted model charges the Task Envelope default approved profile as `policy-default`. Each dispatch reserves fixed units once before startup. After startup the system never reads, infers, or stores host runtime model identity or reasoning effort, and those facts cannot trigger a top-up, refund, or reinterpretation of the outcome.

Role metrics differ. Child self-reports remain pending until the parent coordinator finalizes them with SHA-256 evidence references. Offline calibration compares outcome value per reserved unit between approved profiles and cannot recommend a route change without sufficient adjacent-profile samples. Every proposal retains `execution_authorization=NONE`.

Event V2 and Budget V1 chains from V7.4.2 and earlier remain byte-for-byte verifiable, but the new runtime opens them read-only and projects only allowed fields. Historical model-identity fields never reach V3 events, snapshots, assessments, proposals, or release reports. New records use separate V3/V2 chains and cannot be mixed with legacy chains.

## 5. Codex 0.154.0 scope

V7.6.2 supports Codex CLI 0.154.0 and the ten preceding stable releases exactly as frozen in `config/codex-compatibility-v1.json`. Upstream 0.154.0 fixes Astra visibility in the bundled model picker, makes Astra the bundled default when no model is explicitly configured, and limits async-question guidance to sessions where the tool is available. These changes do not alter the frozen Plugin/Hook contract or the automatic subagent policy, which remains limited to Luna/Terra profiles. The local Marketplace manifest requires `interface.displayName`; future, prerelease, and other out-of-window hosts are not admitted automatically.

Installation is established only when Plugin readback reports `installed=true`, `enabled=true`, and `version=7.6.2`, and the schema-3 host snapshot is `HOST_COMPATIBLE`.

## Feedback and measured benefits

V7.6 retains the validation feedback introduced in V7.5, health gates, opt-in incremental analysis, per-ledger scenario calibration, testable hypotheses, and verified benefit closure. V7.6.2 no longer injects a binding from asynchronous UserPromptSubmit; identity is supplied explicitly by the current repository-external execution envelope. Follow the [controlled evolution operations manual](../locales/en/docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md). Automation remains disabled until explicitly enabled for the project.

## Capability reuse and optional gates

Use the [capability index](CAPABILITY_INDEX.en.md) for bounded initial scans and incremental updates. Recheck candidate source, semantic compatibility, and maintenance cost before reuse. Project gates are disabled by default. With an explicitly enabled policy, V7.7.1 routes canonical `apply_patch` through Operation v2: A creates an origin and is denied, a different B claims permission after preparation, and only B's matching PostToolUse receipt can complete verification. Legacy GateTask never becomes a new permit. See the [acceptance protocol](COMPONENT_REUSE_ACCEPTANCE.en.md) and [release validation](releases/v7.7.1/VALIDATION_REPORT.en.md).
