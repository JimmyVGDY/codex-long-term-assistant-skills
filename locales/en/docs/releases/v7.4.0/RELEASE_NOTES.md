# V7.4.0 Release Notes

V7.4.0 gives Reviewer, Explorer, and Worker one root-task weighted budget, explicit fail-closed dispatch permits, parent-finalized role calibration, and proposal-only offline replay. A controlled budgeted task sets both `CP_DELEGATION_BUDGET_PATH` and `CP_DELEGATION_BUDGET_REQUIRED=1`; without explicit activation, only the model ceiling runs and no budget-gate PASS is claimed. It targets Codex CLI 0.153.0 and generates the required local Marketplace `interface.displayName`.

The current stable plus ten preceding stable compatibility window is deferred to V7.4.1. Automatic routing still stops at Terra High, started agents are never refunded, and every optimization proposal retains `execution_authorization=NONE`.
