# V7.4 Operating Guide

Chinese: [`USER_GUIDE_V7.4.md`](USER_GUIDE_V7.4.md)

## 1. What changed

V7.4.0 places Reviewer, Explorer, and Worker under one root-task weighted budget. The Task Envelope declares the class, `delegation-budget.py` owns the repository-external append-only ledger, the PreToolUse Hook reserves atomically before dispatch, and the Reviewer controller keeps rounds and findings without charging the total budget twice.

Weights are fixed at `luna-low=1`, `luna-medium=2`, `terra-medium=4`, and `terra-high=8`.

| Class | Units | Dispatches | Parallel | Depth | Terra High |
|---|---:|---:|---:|---:|---:|
| LIGHT | 4 | 2 | 1 | 1 | 0 |
| STANDARD | 16 | 6 | 3 | 2 | 1 |
| STRICT | 32 | 10 | 3 | 2 | 1 |

## 2. Workflow

1. Initialize the Task Envelope and choose a budget class.
2. Initialize DelegationBudget V1 outside the repository.
3. Record an `INLINE` or `DELEGATE` decision before every dispatch. A delegated call needs a controlled reason and an opaque unique dispatch key.
4. In the Codex host launch environment, point `CP_DELEGATION_BUDGET_PATH` at the ledger and also set `CP_DELEGATION_BUDGET_REQUIRED=1`. PreToolUse permits the call only when the stable host dispatch ID, role, profile, and permit agree; required mode fails closed when the ledger path is missing.
5. Start/Stop reconciliation occurs only when the host propagates `reservation_id`. Codex 0.153.0 omits it in the observed path, so the reservation remains `RESERVED`; time-order guessing is forbidden.
6. Only host proof that an agent did not start can release a reservation. A started agent is never refunded.

V7.4.0 does not create a root-task ledger automatically. The unified budget is activated explicitly per task. Without both environment variables, the Hook still enforces the automatic model ceiling, but that task must not be reported as having passed the unified budget gate.

## 3. Routing contract

Allowed reasons are `INDEPENDENT_EVIDENCE_GAIN`, `SEMANTIC_COMPLEXITY`, `EVIDENCE_CONFLICT`, `SECURITY_OR_CONCURRENCY_RISK`, `LOWER_TIER_INCONCLUSIVE`, `MISSING_EVIDENCE`, and `INLINE_SUFFICIENT`.

Missing evidence cannot justify an upgrade. Inconclusive lower-tier work must reference the preceding tier and may advance only one step. Terra High requires a security/concurrency risk or a referenced stepwise escalation. Unknown roles and invalid inputs fail closed.

## 4. Runtime evidence and calibration

An omitted model charges the Task Envelope default as `policy-default`; it is not verified runtime evidence. Only a reservation-bound trusted host attestation carrying both model and reasoning effort can cause an actual-profile top-up.

Role metrics differ. Child self-reports remain pending until the parent coordinator finalizes them with SHA-256 evidence references. Offline replay cannot recommend a route change without verified adjacent-tier samples. Every proposal retains `execution_authorization=NONE`.

## 5. Codex 0.153.0 scope

V7.4.0 targets Codex CLI 0.153.0, whose local Marketplace manifest requires `interface.displayName`. The current-plus-ten stable compatibility window is explicitly deferred to V7.4.1.

Installation is established only when Plugin readback reports `installed=true`, `enabled=true`, and `version=7.4.0`.
