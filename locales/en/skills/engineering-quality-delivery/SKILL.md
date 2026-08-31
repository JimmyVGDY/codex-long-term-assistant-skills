---
name: engineering-quality-delivery
description: Use when behavior changes or work includes validation, Git, approval, release, rollback, restart, deployment, or production boundaries.
---

# Engineering Quality and Delivery

1. Select a proportionate `LIGHT`, `STANDARD`, or `STRICT` execution profile.
2. Bind non-trivial work to project, branch, baseline, objective, non-goals, authorization, acceptance criteria, and stop conditions.
3. Use one pre-implementation gate only when public contracts, migrations, access control, core state, cross-service behavior, or production risk needs independent judgment.
4. Make the smallest sufficient change and run the lowest directly relevant validation.
5. A changed baseline invalidates affected validation, Review Packets, and review conclusions.
6. Treat commit, push, deployment, restart, data write, production operation, and effective state as separate authorization and readback boundaries.
7. Regenerate final status from current evidence; never promote modified to deployed or effective.

Use Luna for mechanical evidence collection, Terra Medium for ordinary delivery judgment, and Terra High only for production, irreversible migration, complex rollback, or blocking conflicts. Stronger process gates do not automatically increase model effort.
