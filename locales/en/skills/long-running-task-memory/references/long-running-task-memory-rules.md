# External Memory, Persistent Checkpoints, and Knowledge Promotion for Long-Running Tasks

> V5.0 continues to load references on demand and separates Task Checkpoints, Project Memory, and Cross-Project Knowledge explicitly.

## Loading Index

| Reference | Contents | When to Read |
|---|---|---|
| `memory-principles-layout.md` | External-memory principles, directories, and document responsibilities | Enabling long-term memory, initializing directories, or choosing documents |
| `memory-checkpoints.md` | Activation conditions, small recoverable nodes, checkpoint transactions, and before/after checkpoints for high-risk work | Advancing a task, persisting a node, or recording a high-risk operation |
| `memory-projection-governance.md` | Checkpoint projection, Project Memory promotion, and knowledge candidates | Retaining stable project facts or cross-project experience |
| `memory-multiagent-events.md` | Single-writer multi-agent rules and event-driven document updates | Parallel agents, reviewer results, or updates to plans, decisions, and handoffs |
| `memory-recovery-conflicts.md` | Recovery protocol and state-conflict handling | Context compaction, session recovery, or conflict among project, branch, code, and documents |
| `memory-security-lifecycle.md` | Repository isolation, minimization, security, retention, and archiving | Sensitive information, permissions, lifecycle, archiving, and completion review |

## Loading Principles

- Identify the primary problem domain for the current phase, then read only the minimum necessary references.
- A Task Checkpoint supports recovery of the current task only. Project Memory contains reviewed stable facts for this project only. A Knowledge Candidate remains an unreviewed cross-project candidate.
- After a phase ends, stop treating unrelated fragments as active context.
- Current code, configuration, Git state, logs, and runtime results always take precedence over historical memory.
