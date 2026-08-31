# External-Memory Principles, Directory Layout, and Document Responsibilities

## Contents

- 1. Design Principles
- 2. Directory Convention
- 3. Document Responsibilities and Write Modes

## 1. Design Principles

### 1.1 External Memory First

Conversation context, model-internal memory, and compacted summaries are temporary working caches for the current small node. They are not the sole source of state for a long-running task.

Goals, authorization, progress, evidence, decisions, blockers, and the next action must be written continuously to local external memory so the task remains recoverable after context compaction, session interruption, model switching, or agent switching.

### 1.2 Minimum Loss Window

The desired recovery boundary is:

> If context is compacted or interrupted unexpectedly, at most the current unfinished node without a checkpoint may be lost. Every earlier completed node must already be persisted.

Therefore:

```text
MAX_UNPERSISTED_COMPLETED_NODES = 0
```

A completed small node must not exist only in the current conversation.

### 1.3 Two Kinds of Truth

#### Task-Control Truth

Maintained by current task instructions and external memory:

- goals and non-goals;
- permitted and prohibited scope;
- authorization boundaries;
- phases and nodes;
- completed work, blockers, and next action.

#### Technical-Fact Truth

Determined by actual state:

- current code and configuration;
- Git branch, HEAD, workspace, and diffs;
- database, middleware, and file state;
- builds, tests, logs, monitoring, and runtime results.

External documents determine how the plan should continue; they cannot override what the system actually is.

### 1.4 Built-In Memories Are Supporting Evidence Only

Even when Codex Memories, Chronicle, or another automatic memory is enabled, it must not be the sole source for hard task rules, real-time progress, or delivery evidence. Automatic memory may be delayed, omit an active session, or contain only a summary. This mechanism remains the deterministic source of current task state.

---

## 2. Directory Convention

Use a configurable root placeholder:

```text
<AGENT_CONTEXT_ROOT>/<project-id>/
```

Recommended layout:

```text
<AGENT_CONTEXT_ROOT>/<project-id>/
├── PROJECT_CONTEXT.md
├── CURRENT_TASK.md
├── PLAN.md
├── PROGRESS.md
├── DECISIONS.md
├── HANDOFF.md
├── KNOWN_ISSUES.md
├── DELIVERY_RECORD.md
├── reviews/
│   └── <task-id>/
│       ├── round-01/
│       ├── round-02/
│       └── round-03/
└── archive/
    └── <task-id>/
```

`<AGENT_CONTEXT_ROOT>` is defined by the current machine, Codex Home, project configuration, or requester. Global rules must not hard-code a user name, Windows, WSL, or Linux path, or a specific project.

Reuse an existing local document with the same responsibility instead of creating a synonymous duplicate.

---

## 3. Document Responsibilities and Write Modes

| Document | Purpose | Write Mode | Update Trigger |
|---|---|---|---|
| `PROJECT_CONTEXT.md` | Stable project facts, technology stack, and hard constraints | Infrequent revision | A new long-lived fact is confirmed |
| `CURRENT_TASK.md` | Latest snapshot of the current task | Replace | Every checkpoint |
| `PLAN.md` | Phases, dependencies, risks, validation, and review plan | State revision | Plan or phase change |
| `PROGRESS.md` | Append-only checkpoints and evidence index | Append | Every checkpoint |
| `DECISIONS.md` | Important architecture, compatibility, and business decisions | Append | Key decision |
| `HANDOFF.md` | Minimum recovery snapshot after pause, compaction, or switching | Replace | Handoff or pause |
| `KNOWN_ISSUES.md` | Issues outside current scope | State revision | Out-of-scope issue found or resolved |
| `DELIVERY_RECORD.md` | Task records that became actual deliverables | Append | Delivery occurs |
| `reviews/` | Raw structured subreviewer results | Independent files | Multi-agent review |

### 3.1 Hot Documents

Read fully first during recovery:

- `CURRENT_TASK.md`;
- the current phase in `PLAN.md`;
- the latest three checkpoints in `PROGRESS.md`.

### 3.2 Warm Documents

Read by reference:

- relevant ADRs in `DECISIONS.md`;
- reports for the relevant round under `reviews/`;
- relevant items in `KNOWN_ISSUES.md`.

### 3.3 Cold Archive

When active `PROGRESS.md` exceeds 20 checkpoints, archive older records by task and range:

```text
archive/<task-id>/PROGRESS-CP001-CP020.md
```

Keep only an index and recent checkpoints in active `PROGRESS.md`. Do not reload the complete history during every recovery.

---
