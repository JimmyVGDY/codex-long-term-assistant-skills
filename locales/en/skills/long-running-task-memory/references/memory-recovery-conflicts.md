# Recovery Protocol and State-Conflict Handling

## 11. Fixed Recovery Protocol

After context compaction, session recovery, a model change, a coordinating-agent change, or a long pause, do not resume modifications immediately.

Follow this order:

1. Read the current request and authorization.
2. Read platform, global, and project-level `AGENTS.md` files.
3. Read `PROJECT_CONTEXT.md`.
4. Read `CURRENT_TASK.md`.
5. Read the active phase in `PLAN.md`.
6. Read the latest three checkpoints in `PROGRESS.md`.
7. Follow references to relevant `DECISIONS.md` entries and reviewer reports.
8. Read `HANDOFF.md` when needed.
9. Run `git status`.
10. Confirm branch, HEAD, baseline, and untracked files.
11. Inspect `git diff`, `git diff --stat`, and recent commits.
12. Compare documented state with the actual repository.
13. Re-read the core code, configuration, and tests involved in the “single next action.”
14. Continue only after resolving all conflicts.

```text
RECENT_CHECKPOINTS_TO_LOAD = 3
```

Never modify code based solely on `HANDOFF.md`, an automatic summary, Codex Memories, or an old chat conclusion.

---

## 12. State Conflicts

Stop and reconcile when:

- the current branch differs from the document;
- the HEAD commit differs;
- the Git diff exceeds the recorded scope;
- another agent or external actor changed files;
- a document says tests passed but affected code changed later;
- someone else already completed the planned next action;
- authorization, environment, or data target is unclear;
- documents conflict with runtime state.

Resolution process:

1. Record a “state divergence” checkpoint.
2. Describe the conflict precisely.
3. Treat actual code, configuration, Git, and runtime results as authoritative.
4. Revalidate affected conclusions.
5. Correct the documents.
6. Define a new next action.

Old test evidence expires automatically when related code changes and must be marked “Revalidation required.”

---
