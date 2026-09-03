# V7.4.0 Release Notes

Version: 7.4.0  
Target host: Codex CLI 0.153.0

## Highlights

- Reviewer, Explorer, and Worker share one root-task DelegationBudget V1 with fixed profile weights `1/2/4/8`.
- LIGHT, STANDARD, and STRICT start at `4/16/32` weighted units and also bound dispatches, parallel reservations, nesting depth, and Terra High use.
- PreToolUse reserves atomically only when an explicit dispatch permit, stable host dispatch ID, role, and profile agree. Corrupt ledgers, unknown roles, and exhaustion fail closed.
- The unified budget is activated explicitly per root task by setting both `CP_DELEGATION_BUDGET_PATH` and `CP_DELEGATION_BUDGET_REQUIRED=1`. Without activation, only the model ceiling runs and no budget-gate PASS is claimed.
- Nested agents charge the same root. A started agent is never refunded; only host proof of not starting can release a reservation.
- An omitted model charges the Task Envelope default as `policy-default`. Ordinary Hook fields are not trusted runtime-model evidence.
- The Reviewer controller keeps rounds, findings, isolation, and stop state while DelegationBudget exclusively owns total charging.
- Each role has separate value metrics. Child self-reports cannot finalize samples. Adjacent-tier offline replay makes no change with insufficient data, and every proposal retains `execution_authorization=NONE`.
- Local Marketplace generation now includes the `interface.displayName` required by Codex 0.153.0.

## Compatibility boundary

V7.4.0 declares Codex CLI 0.153.0 only. The requested current stable plus ten preceding stable versions window is explicitly deferred to V7.4.1.

## Unchanged boundaries

Automatic routing stops at `gpt-5.6-terra + high`; Sol, `xhigh`, `max`, and `ultra` remain forbidden. The ledger stores no prompt, answer, code, diff, token, or credential. A passing budget is not proof of runtime model, task outcome, or output value. Evolution never modifies policy automatically.
