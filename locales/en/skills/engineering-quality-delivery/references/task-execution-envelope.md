# Task Execution Envelope

The Task Envelope is the minimum deterministic control object for a nontrivial task. It carries consistent facts among the coordinating session, independent-context subagents, external memory, and recovery.

## Required Fields

- `task_id`, project ID, Project Profile, repository root, and Project Binding hash;
- six independent routing dimensions: `complexity`, `project_stage`, `execution_profile`, `reviewer_budget`, `model_profile`, and `host_surface`;
- goals, non-goals, permitted scope, and prohibited scope;
- primary skill, supporting skills, deferred skills, and unique responsibilities;
- separate authorization for modification, commit, push, deploy, restart, data writes, and making functionality effective;
- required gates, stopping conditions, rollback conditions, and acceptance criteria;
- Git baseline, current diff fingerprint, evidence, review-packet hash, action readback, and finalization state.

## Rules

1. A `LIGHT` task may keep a simplified envelope in the current response; `STANDARD` and `STRICT` should normally persist it.
2. Cross-session, protected, or long-running work should bind an external Project Profile. Project ID, repository, or Profile-hash mismatch fails closed.
3. Long-running tasks put an envelope summary in `CURRENT_TASK.md`; `execution_guard.py` maintains complete machine state.
4. Send a subagent only the envelope fields relevant to its responsibility and the common review packet, not the full chat history.
5. Update the envelope when permissions, scope, phase, baseline, or evidence freshness changes. Do not reuse old approval, evidence, or review packets.
6. The envelope cannot override actual code, Git, configuration, or runtime results; conflicts enter `RECOVER` or `BLOCKED`.

## Format versions and ownership

| Object | Current format | Source |
|---|---|---|
| Task Envelope template | schema <!-- cp-fact:schema.envelope -->3<!-- /cp-fact --> | `../assets/templates/TASK_EXECUTION_ENVELOPE.template.yaml` and package manifest |
| execution-state | schema <!-- cp-fact:schema.execution-state -->4<!-- /cp-fact --> | SCHEMA in `../scripts/execution_guard.py` |
| Embedded delegation_budget binding | schema 1 | execution_guard routing declaration |
| External DelegationBudget ledger | <!-- cp-fact:schema.budget -->2.0<!-- /cp-fact --> | Root-task budget runtime |

These objects have distinct format versions, independent of the package version. Reviewer state owns reviews, not the root-task budget.
