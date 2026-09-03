# V7.4 Operating Guide

Chinese: [V7.4 operating guide](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/USER_GUIDE_V7.4/)

V7.4.1 preserves one root-task weighted DelegationBudget for Reviewer, Explorer, and Worker. Weights are `1/2/4/8`; LIGHT, STANDARD, and STRICT provide `4/16/32` total units.

Every delegated call needs a controlled route reason and explicit dispatch permit. For a controlled budgeted task, the host launch environment must set both `CP_DELEGATION_BUDGET_PATH` and `CP_DELEGATION_BUDGET_REQUIRED=1`. PreToolUse atomically reserves before dispatch and fails closed on exhaustion, invalid roles, missing stable dispatch identity, missing required ledger configuration, or ledger corruption. Started agents are never refunded. Missing Start/Stop correlation remains unavailable rather than being guessed.

V7.4.1 does not create a root-task ledger automatically. Without task-scoped explicit activation, only the automatic model ceiling is active and the unified budget gate must not be reported as passed.

Child self-reports cannot finalize calibration. Only parent-finalized samples with evidence references enter offline adjacent-tier replay, and every resulting proposal keeps `execution_authorization=NONE`.

V7.4.1 supports Codex CLI 0.153.0 and the ten preceding stable releases exactly as frozen in the compatibility registry. Installation is complete only after Plugin readback reports `installed=true`, `enabled=true`, and `version=7.4.1`, and the schema-3 host snapshot is `HOST_COMPATIBLE`.
