# Activation, Small Recoverable Nodes, Checkpoint Transactions, and High-Risk Before/After Checkpoints

## Contents

- 4. Activation and Minimum Document Set
- 5. Independently Recoverable Small Nodes
- 6. Checkpoint Transactions
- 7. The Current Snapshot in CURRENT_TASK
- 8. Before and After Checkpoints for High-Risk Operations

## 4. Activation and Minimum Document Set

Enable this workflow when any of the following applies:

- work spans multiple sessions or days;
- there are three or more implementation phases;
- multiple modules, services, repositories, or worktrees are involved;
- data migration, historical compatibility, or major architecture change is involved;
- production, staged rollout, rollback, or an observation period is involved;
- validation includes many tests, multi-agent review, or performance work;
- context is already long or likely to be compacted;
- the requester explicitly requires persistent records at each node;
- work must resume precisely after interruption.

The minimum document set is:

```text
CURRENT_TASK.md
PROGRESS.md
```

For a multistep task, add:

```text
PLAN.md
```

Create other documents when their events occur; do not generate every template mechanically.

Normally do not enable this workflow for:

- a small single-method repair that fits one session;
- a simple explanation or one-time command lookup;
- narrowly scoped static analysis;
- a short answer without code changes;
- commit splitting or commit-message correction alone.

When the requester explicitly requires persistent checkpoints, follow that constraint even for a seemingly small task.

---

## 5. Independently Recoverable Small Nodes

### 5.1 Definition

A “small node” is the smallest unit with explicit input, operation, output, evidence, and next action that can serve as an independent recovery point.

### 5.2 Nodes That Require Checkpoints

- A module, call chain, or data flow has been read completely and a clear conclusion formed.
- A root cause is confirmed or an important candidate excluded.
- A group of code changes within one functional boundary is complete.
- A build, targeted test, minimum reproduction, or exported sample validation is complete.
- A database migration or repair script is designed, executed, or validated.
- A multi-agent review round is dispatched.
- One reviewer round is collected and consolidated.
- A minimum complete repair set is defined.
- A batch of centralized repairs is complete.
- A key technical or business decision is made.
- A new blocker, failure, scope change, or authorization change appears.
- A commit, push, deployment, restart, or environment validation completes.
- Work is about to pause, wait for requester confirmation, or end the current session.

### 5.3 Events That Normally Do Not Need Their Own Checkpoint

- One `ls`, `grep`, `find`, or short file read.
- Temporary reading before a conclusion exists.
- A punctuation change or immediately reverted attempt.
- Repeating a check without a state change.
- A subagent's intermediate reasoning.

### 5.4 Prevent Long Gaps Without Checkpoints

If no complete small node exists after eight consecutive substantive actions, write an “in-progress checkpoint.”

Substantive actions include:

- modifying code or configuration;
- running a build or test;
- running a script that changes local state;
- reaching an implementation-affecting conclusion;
- dispatching or collecting subagents;
- handling databases, caches, messages, files, or environments;
- changing plan, scope, or authorization interpretation.

```text
MAX_SUBSTANTIVE_ACTIONS_WITHOUT_CHECKPOINT = 8
```

---

## 6. Checkpoint Transaction

Perform each checkpoint in this order:

1. Re-read `CURRENT_TASK.md` and the tail of `PROGRESS.md` to avoid overwriting another update.
2. Generate a unique checkpoint ID such as `CP-20260729-001`.
3. Confirm what actually completed and its evidence.
4. Append the checkpoint to `PROGRESS.md` first.
5. Refresh the latest snapshot in `CURRENT_TASK.md` second.
6. Verify that both documents end with the same checkpoint ID.
7. Compute a content fingerprint. If the last checkpoint in the same workspace has identical content, record no change and skip a duplicate append.
8. Continue to the next node only after both writes succeed.

### 6.1 Checkpoint Content

Record at least:

- checkpoint ID, time, and time zone;
- task, phase, node type, and executing agent;
- objective of this node;
- work actually completed;
- confirmed facts and evidence levels;
- modified files and important symbols;
- actual commands and result summaries;
- validation, review, and environment state;
- failures, blockers, risks, and unverified items;
- effects on plan and scope;
- one next action.

### 6.2 The Next Action Must Be Executable

Do not write:

```text
Continue optimizing
Continue processing
Continue testing
```

Instead write:

```text
Re-read OrderService.updateStatus() and its three callers,
confirm whether the new idempotency check affects legacy state writeback,
and run the targeted Service tests.
```

### 6.3 Atomic Writes

When supported:

- update `CURRENT_TASK.md` by atomically replacing a temporary file;
- refresh and confirm `PROGRESS.md` after appending;
- never claim a checkpoint completed when a write failed.

The optional `scripts/checkpoint.py` supports `init`, `append`, `validate`, `recover`, `repair`, and `archive`. `append` skips consecutive duplicate checkpoints with the same workspace and content by default; use `--force-append` only when an audit requires a repeated snapshot. Shared writes use a lock file. After a crash, remove a stale lock only after confirming no other writer exists. If the script is unavailable, maintain equivalent information manually.

---

## 7. Current Snapshot in CURRENT_TASK

`CURRENT_TASK.md` must remain short, current, and directly recoverable; keep it within approximately 250 lines.

At minimum, include:

- state version;
- latest checkpoint ID and update time;
- project, task, branch, baseline, and current HEAD;
- workspace-diff summary and untracked files;
- current goals, non-goals, scope, and authorization;
- current phase and node;
- recently completed node;
- current blockers and unverified items;
- multi-agent review round, depth, and budget;
- one next action;
- actual state that must be checked before recovery.

Do not put complete logs, long reports, or full history into `CURRENT_TASK.md`.

---

## 8. Before and After Checkpoints for High-Risk Operations

Use these for:

- production writes;
- database DDL, DML, or data repair;
- deletion or migration in Redis, message queues, object storage, or files;
- Git commits, pushes, or force operations;
- deployment, restart, scaling, or traffic switching;
- broad automated rewrites;
- dispatching a multi-agent review;
- any irreversible or partially successful operation.

### 8.1 Before-Operation Checkpoint

Record:

- intended action;
- target environment, service, instance, file, or data scope;
- current state and authorization;
- expected impact;
- backup and rollback;
- acceptance and stopping conditions;
- confirmation that the operation has not started.

### 8.2 After-Operation Checkpoint

Record:

- command or action actually executed;
- success, failure, or partial success;
- actual impact scope;
- whether rollback occurred;
- current true state;
- next validation.

If context is interrupted mid-operation, a recovering agent must be able to determine whether the operation was not started, running, partially complete, complete, or rolled back.

---
