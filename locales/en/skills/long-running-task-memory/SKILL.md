---
name: long-running-task-memory
description: Use for cross-session, multi-stage, multi-module, multi-repository, multi-agent, observation-window, and context-compaction work that needs recoverable checkpoints.
---

# Long-Running Task Memory

1. Keep task control state, authorization, evidence, and next action in a repository-external agent directory. Code, Git, configuration, and runtime results remain the technical source of truth.
2. Maintain `CURRENT_TASK.md` and `PROGRESS.md`; add `PLAN.md` for multi-stage work.
3. Write event-driven checkpoints at recoverable nodes, before and after high-risk actions, and before pause or context compaction.
4. Use content fingerprints to deduplicate unchanged checkpoints. Archive older active checkpoints after the bounded hot set grows beyond 20.
5. Use a single shared-memory writer. Subagents return structured facts and do not edit shared memory.
6. Recover from the current task, current plan stage, three recent checkpoints, Project Binding, live Git, and runtime state.
7. Task checkpoints do not automatically become Project Memory; project records do not automatically become cross-project knowledge.
8. Scan for credentials and maintain retention and access boundaries.

Persist verified facts, evidence grade, authorization, state, blockers, risk, and next action—not hidden reasoning. This Skill normally uses Luna and does not create subagents by itself.

## Controlled-Evolution Boundary

This Skill supplies reviewed checkpoints and recovery evidence to cross-task analysis; it does not maintain the evolution contract. Route governance of repeated failures, model cost, Reviewer yield, or Skill-routing deviation to `controlled-evolution-governance`. Ordinary long-running work must not load evolution rules.
