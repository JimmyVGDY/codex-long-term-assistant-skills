# Single-Writer Multi-Agent Memory and Event-Driven Document Updates

## 9. Single Writer for Multi-Agent Work

### 9.1 Coordinating Agent

Only the coordinating agent may update shared:

- `CURRENT_TASK.md`;
- `PLAN.md`;
- `PROGRESS.md`;
- `DECISIONS.md`;
- `HANDOFF.md`;
- `KNOWN_ISSUES.md`;
- `DELIVERY_RECORD.md`.

### 9.2 Subagents

Subagents:

- return structured results only; or
- write only an explicitly assigned independent file, for example:

```text
reviews/TASK-XXX/round-01/security.md
```

- do not edit shared task documents directly;
- do not overwrite another agent's records;
- do not write internal reasoning into documents.

### 9.3 Reviewer Isolation State

Shared task state must record:

- the reviewer TOML configuration declaration;
- the parent session's actual sandbox;
- current isolation level: `system-readonly`, `logical-readonly`, `self-review`, or `unknown`;
- whether strict read-only mode was used;
- whether strict read-only eligibility was met;
- the isolation evidence file or controlled probe result.

Do not treat “the reviewer wrote no files” or a TOML `read-only` declaration as proof of system isolation. When the parent session is writable, record `logical-readonly` by default.

### 9.4 Multi-Agent Checkpoints

Merge events and persist at least these four recoverable nodes:

1. The review packet, reviewer plan, model tier, and budget are fixed, and round one is dispatched.
2. All round results are collected and consolidated by root cause.
3. Centralized repair and affected validation are complete.
4. Final targeted review and gate conclusions are complete.

Do not create a separate checkpoint merely for dispatching one reviewer, receiving an intermediate result, or polling unchanged status. Still checkpoint immediately for a blocker, authorization change, or high-risk operation.

---

## 10. Event-Driven Document Updates

### 10.1 Plan Changes

Update `PLAN.md` when:

- a phase is added, removed, blocked, or rolled back;
- dependencies change;
- validation, review, staged rollout, or rollback changes;
- the requester changes goals or scope.

### 10.2 Key Decisions

Update `DECISIONS.md` with:

- context and confirmed facts;
- candidate options;
- selection reasons;
- impact, compatibility, performance, and cost;
- risks, defenses, and rollback;
- reevaluation conditions.

### 10.3 Out-of-Scope Issues

Update `KNOWN_ISSUES.md` with evidence level, impact, and reason for deferral. Do not expand the task autonomously.

### 10.4 Handoff or Pause

Update `HANDOFF.md` with the minimum complete snapshot needed by an agent that has not read the old chat.

### 10.5 Actual Delivery

Update `DELIVERY_RECORD.md` with actual deliverables, tests, reviews, CHANGELOG, commits, pushes, deployments, restarts, effective state, and residual risk.

Temporary experiments, formatting-only changes, and rolled-back attempts that were not delivered do not enter the formal delivery record.

---
