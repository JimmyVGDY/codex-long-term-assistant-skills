# Engineering Quality, Validation, Production, and Git Delivery Workflow

> V5.0 continues on-demand loading and adds project identity binding, separation of approval and evidence, and final-state readback. Read this index first and load only the fragments needed by the current task.

## Loading Index

| Reference | Contents | When to Read |
|---|---|---|
| `quality-task-planning.md` | Task classification, prechange planning, and preimplementation gates | Task start, scope confirmation, implementation planning, or high-risk design review |
| `execution-profiles-and-phases.md` | `LIGHT/STANDARD/STRICT` and execution phases | Selecting gates and phase transitions |
| `task-execution-envelope.md` | Task Envelope V2, Project Binding, and six-dimensional routing | Nontrivial, cross-session, or protected-operation work |
| `evidence-fingerprint-protocol.md` | Repository fingerprints, evidence freshness, and invalidation | Validation, review, baseline change, and delivery decisions |
| `project-binding-approval-finalization.md` | Project binding, approval, action readback, and finalization | Commit, push, deploy, restart, data writes, and final reporting |
| `quality-validation-gates.md` | Test selection, minimum validation, adversarial and performance gates | Validation after code, script, frontend, or migration changes |
| `quality-review-completion.md` | Postimplementation review and completion definition | Independent review and completion after code and validation stabilize |
| `quality-production-operations.md` | Safe production operations | Production reads, writes, releases, restarts, stopping, and rollback |
| `quality-git-delivery.md` | Git, change records, and final delivery | Commits, pushes, documentation, delivery reports, and stopping points |

## Loading Principles

- Identify the primary problem domain for the current phase, then read the minimum necessary references.
- Project identity, task state, review packet, checkpoint, and Project Memory each have one owner; do not copy them manually into competing sources of truth.
- After a phase ends, stop treating unrelated fragments as active context.
- Actual code, configuration, Git state, logs, and runtime results always take precedence over general rules.
