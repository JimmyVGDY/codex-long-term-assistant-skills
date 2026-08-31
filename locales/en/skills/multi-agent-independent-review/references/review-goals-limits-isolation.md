# Review Goals, Budgets, and Runtime Isolation

## 1. Goal

Multi-agent review independently covers important risks; it does not maximize reviewer count:

> Discover once, attribute consistently, repair centrally, reuse evidence, and rereview only affected areas.

The coordinating agent alone dispatches, budgets, consolidates, and makes the final decision. Reviewers do not modify the workspace, maintain shared ledgers, or spawn further agents.

## 2. Conservative Default Budget

```text
MAX_REVIEW_AGENT_DEPTH = 2
MAX_PREIMPLEMENTATION_REVIEW_ROUNDS = 1
MAX_PREIMPLEMENTATION_REVIEWERS = 2
MAX_POST_REVIEW_ROUNDS = 2
MAX_PARALLEL_REVIEWERS = 3
MAX_TOTAL_REVIEW_AGENTS_PER_BOUNDARY = 6
MAX_REPAIR_ROUNDS = 2
MAX_TERRA_HIGH_REVIEWERS = 1
```

Meaning:

- depth 0 is the coordinator, depth 1 is a specialist reviewer, and depth 2 is reserved for blocking conflicts or targeted rereview;
- preimplementation review has at most one round and normally one or two reviewers;
- postimplementation review has at most two rounds by default, with up to three reviewers in round one and two in the next round;
- one functional boundary uses at most six reviewers in total;
- at most one `terra-high` reviewer is used by default.

For exceptional critical work, the controller retains V4.1 hard ceilings: depth 3, three postimplementation rounds, six parallel reviewers, twelve total reviewers, three repair rounds, and two `terra-high` reviewers. Relaxation requires explicit configuration and a written risk reason; a prompt cannot trigger it automatically.

Use a lower platform, task, or project limit whenever it exists. Do not evade budgets through equivalent split calls, renamed reviewers, or recreated ledgers.

## 3. Model Budget

Automatic reviewers may use only `luna-low`, `luna-medium`, `terra-medium`, or `terra-high`. See `reviewer-model-routing.md` for routing, escalation, and runtime evidence.

Control model, reviewer count, context, and rounds together. Multiple reviewers can amplify total cost even when none exceeds Terra High.

## 4. Runtime Isolation

TOML `sandbox_mode = "read-only"` expresses configuration intent only. Record the parent session's actual sandbox, confirmed agent type, controlled probe, and final isolation level separately:

| Level | Definition | Permitted Claim |
|---|---|---|
| `system-readonly` | Parent session is read-only, or a controlled probe is explicitly denied by the sandbox, and agent type is confirmed | System-isolated review |
| `logical-readonly` | Parent session is writable and the reviewer refrains from writing by instruction | Logically read-only review |
| `self-review` | Implementation agent checks its own work | Not a substitute for independent review |
| `unknown` | Evidence is insufficient | Unverified |

Production, real data, authorization security, money, inventory, and irreversible migrations require `system-readonly` by default. A writable parent session without sandbox-denial evidence can claim only `logical-readonly`.

A controlled write probe may run only in a disposable temporary Git repository. Never probe in the real project, a production directory, an account home directory, or a real-data directory.
