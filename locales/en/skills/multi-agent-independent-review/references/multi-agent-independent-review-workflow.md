# Multi-Agent Independent Review and Cost-Convergence Workflow

> V5.0 keeps the progressive loading introduced in V4.2. Read this index first, then load only references required by the current phase and risk. Do not load every rule at once.

## Loading Index

| Reference | Contents | When to Read |
|---|---|---|
| `review-goals-limits-isolation.md` | Goals, default budgets, hard limits, and runtime isolation | Starting review or defining safety boundaries |
| `reviewer-model-routing.md` | Four-tier Luna/Terra model routing and escalation | Planning or dispatching reviewers |
| `reviewer-effort-tiers.md` | Reviewer counts and context budgets for `economy/balanced/deep` | Selecting review scale |
| `review-triggers-reviewers.md` | Triggers, risk levels, and reviewer responsibilities | Deciding whether to review and selecting roles |
| `review-preimplementation-controller.md` | Preimplementation gates and state controller | Before high-risk implementation |
| `review-postimplementation.md` | Common review packet, parallel consolidation, centralized repair, and targeted rereview | After the diff and minimum validation stabilize |
| `review-stop-output-memory.md` | Stopping, structured results, ledger, and long-term memory | Consolidation, closure, and persistence |

## Minimum Loading Principles

- Load one primary reference for the current step; add a second only for a real cross-domain need.
- Skills, references, and project rules provide methods, not substitutes for actual code, configuration, logs, or runtime evidence.
- A reviewer reads the packet summary and scope statistics first, expanding to full diffs and dependencies only when evidence requires it.
- Rules for completed phases do not remain in active context. The coordinating session retains only structured summaries and evidence indexes.
