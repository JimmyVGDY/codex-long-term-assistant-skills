# Governance of Checkpoints, Project Memory, and Knowledge Candidates

## 1. Three Fact Boundaries

| Layer | Purpose | Direct Reuse Scope |
|---|---|---|
| Task Checkpoint | Restore the current task's phase, evidence, blockers, and next action | Current task |
| Project Memory | Explicitly reviewed stable project facts, decisions, and constraints | Same project |
| Knowledge Candidate | Redacted candidate for a general pattern | Must not be applied automatically before review |

A checkpoint, chat summary, or single reviewer conclusion cannot become Project Memory automatically.

## 2. Promotion Path

```text
Task Checkpoint / Evidence
  -> Memory Projection Candidate
  -> explicit review in reviewed_by
  -> Project Memory
  -> review of redaction, applicability, counterexamples, and evidence
  -> Knowledge Candidate
  -> external governance decides whether to activate it
```

`cp-runtime.py memory-project` creates candidates only. Only `memory-promote` writes Project Memory, and `knowledge-candidate` still creates a record awaiting review.

## 3. Candidate Content

A candidate should contain only:

- verified facts;
- accepted decisions and reasons;
- stable constraints and risks;
- unresolved items;
- references to source files, evidence, or checkpoints;
- applicable projects and versions plus invalidation conditions.

Never include plaintext credentials, private keys, tokens, personal sensitive information, complete production logs, or lengthy internal reasoning.

## 4. Invalidation and Conflict

When Project Memory conflicts with current code, Git, configuration, or runtime evidence, mark it as a stale candidate and revalidate it. Historical memory must never override current facts. A cross-project candidate must pass applicability matching; sharing a technology name is not enough for automatic reuse.
