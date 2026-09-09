---
name: engineering-quality-delivery
description: Use when behavior changes or work includes validation, Git, approval, release, rollback, restart, deployment, or production boundaries.
---

# Engineering Quality and Delivery

Before adding features, fixing bugs, refactoring, or changing shared implementations, read [Component and Module Reuse](references/component-module-reuse.md) and assess existing capabilities in proportion to the task. Read-only work and changes without behavioral impact do not trigger this rule.

Follow the [shared capability-index workflow](references/capability-index-workflow.md) for applicable actions:

- **Before editing**: with a bound Profile and verified runtime, first query a bounded scope to establish index state; neither a small task nor the absence of index files inside the workspace proves it is missing. Reliable missing-index evidence from this task permits source search when initial scanning does not apply. First-onboarding shared-interface or multi-consumer changes need a bounded initial scan; `INDEX_MISSING` does not waive that trigger, and LIGHT only narrows scope.
- **Before closing**: the task coordinator invalidates changed paths, then scans inspected changed sources plus stale candidate sources actually checked and adopted after querying, and reads back the result. Refresh stale locations even when the reused source was not edited. Invalidation alone is not an update. Subagents return findings for the coordinator to merge.
- A small local fix without an index may search source directly; unrelated tasks create no index. Do not add agents or repository-wide scans for this workflow.

1. Select a proportionate `LIGHT`, `STANDARD`, or `STRICT` execution profile.
2. Bind non-trivial work to project, branch, baseline, objective, non-goals, authorization, acceptance criteria, and stop conditions.
3. Use one pre-implementation gate only when public contracts, migrations, access control, core state, cross-service behavior, or production risk needs independent judgment.
4. Make the smallest sufficient change and run the lowest directly relevant validation.
5. A changed baseline invalidates affected validation, Review Packets, and review conclusions.
6. Treat commit, push, deployment, restart, data write, production operation, and effective state as separate authorization and readback boundaries.
7. Regenerate final status from current evidence; never promote modified to deployed or effective.
8. When the host provides a complete feedback binding and engineering validation is already required, run it through `scripts/evolution.py validate-task`. Before the final reply, the parent uses `finalize-task` to confirm outcome, failure category, repair rounds and routing. Derive counts from evidence without retaining command/output bodies. Missing binding or evidence remains UNKNOWN; do not add meaningless validation or full evolution analysis to ordinary tasks.

Use Luna for mechanical evidence collection, Terra Medium for ordinary delivery judgment, and Terra High only for production, irreversible migration, complex rollback, or blocking conflicts. Stronger process gates do not automatically increase model effort.
