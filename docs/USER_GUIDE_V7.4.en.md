# V7.4 Operating Guide

Chinese: [`USER_GUIDE_V7.4.md`](USER_GUIDE_V7.4.md)

## 1. What changed

V7.4.4 preserves one root-task weighted budget for Reviewer, Explorer, and Worker while tightening model-identity privacy to the pre-dispatch boundary. The Task Envelope declares the class, `delegation-budget.py` owns the repository-external append-only Budget V2 ledger, the PreToolUse Hook reserves the approved profile atomically before dispatch, and the Reviewer controller keeps rounds and findings without charging twice or receiving host runtime model identity.

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

V7.4.4 does not create a root-task ledger automatically. The unified budget is activated explicitly per task. Without both environment variables, the Hook still enforces the automatic dispatch-profile ceiling, but that task must not be reported as having passed the unified budget gate.

## 3. Routing contract

Allowed reasons are `INDEPENDENT_EVIDENCE_GAIN`, `SEMANTIC_COMPLEXITY`, `EVIDENCE_CONFLICT`, `SECURITY_OR_CONCURRENCY_RISK`, `LOWER_TIER_INCONCLUSIVE`, `MISSING_EVIDENCE`, and `INLINE_SUFFICIENT`.

Missing evidence cannot justify an upgrade. Inconclusive lower-tier work must reference the preceding tier and may advance only one step. Terra High requires a security/concurrency risk or a referenced stepwise escalation. Unknown roles and invalid inputs fail closed.

## 4. Approved profile, cost, and calibration

An omitted model charges the Task Envelope default approved profile as `policy-default`. Each dispatch reserves fixed units once before startup. After startup the system never reads, infers, or stores host runtime model identity or reasoning effort, and those facts cannot trigger a top-up, refund, or reinterpretation of the outcome.

Role metrics differ. Child self-reports remain pending until the parent coordinator finalizes them with SHA-256 evidence references. Offline calibration compares outcome value per reserved unit between approved profiles and cannot recommend a route change without sufficient adjacent-profile samples. Every proposal retains `execution_authorization=NONE`.

Event V2 and Budget V1 chains from V7.4.2 and earlier remain byte-for-byte verifiable, but the new runtime opens them read-only and projects only allowed fields. Historical model-identity fields never reach V3 events, snapshots, assessments, proposals, or release reports. New records use separate V3/V2 chains and cannot be mixed with legacy chains.

## 5. Codex 0.153.2 scope

V7.4.4 supports Codex CLI 0.153.2 and the ten preceding stable releases exactly as frozen in `config/codex-compatibility-v1.json`. The local Marketplace manifest requires `interface.displayName`; future, prerelease, and other out-of-window hosts are not admitted automatically.

Installation is established only when Plugin readback reports `installed=true`, `enabled=true`, and `version=7.4.4`, and the schema-3 host snapshot is `HOST_COMPATIBLE`.
