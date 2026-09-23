---
name: multi-agent-independent-review
description: Use for risk-based design gates, independent reviews of behavior changes, or checking system-read-only isolation before review. Exclude routine low-risk self-checks and formatting without behavioral impact; do not dispatch reviewers for formality.
---

# Independent Multi-Agent Review

## Entry and Phase Boundaries

- When checking only the review-isolation gate, read the relevant rules and report available or blocked from host evidence; do not initialize packets or ledgers, or dispatch reviewers. Reading this Skill neither proves system-read-only isolation nor grants authority. Stop when required system isolation cannot be proved.
- Retain the relevant primary domain capability when independently reviewing implementation behavior. Review procedure and quality evidence do not replace domain judgment. Keep cross-phase memory only for current recovery or state maintenance, and explain combinations above the default limit.

The execution steps below apply to actual review after its gate is satisfied.

1. Select the execution profile, shared DelegationBudget, Reviewer effort, and model profile independently. Reviewer state does not charge the total budget twice.
2. Read the root's frozen policy first. Explicit V4 checks scenario qualification, paired gains and actual resources in that order. Its evaluation catalog has 18 combinations; the new production pool has nine GPT-6 profiles. Missing approved qualifications require independent evaluation, not selection by model name. V3 retains its frozen Luna Low scoring. Workers/explorers retain four profiles; automatic effort is capped at High. Read reviewer-model-routing.md.
3. Bind every Review Packet to Project ID, Task ID, Git baseline, Task Envelope, packet hash, validation summary, assigned scope, and a matching Reviewer permit in `delegation-budget.py` when unified accounting is active. For scoped review, also use `scripts/scoped_review.py` to fingerprint targets, statically discovered dependencies, configuration, and authority files. Unknown dynamic dependencies are `INCOMPLETE`, relevant changes are `STALE`, and scoped PASS never means release-wide PASS.
4. Read summary and statistics first, then assigned diff and direct dependencies, then expand only when evidence remains insufficient.
5. Collect one round before deduplication, root-cause clustering, conflict resolution, and centralized repair.
6. After repair, refresh only affected evidence and packet content. Stop repeated review when the packet is unchanged or no new information exists.
7. Defaults: parallel <=3, cumulative <=6, post-implementation rounds <=2 and repair rounds <=2. V3 additionally limits Terra High reviewers to one, Sol/Astra attempts to two with one at a time, and Astra High to one. V4 verifies its fixed root resource vector and complete phase allocation. Apply the stricter root-budget and controller limits.

V4 uses the repository-root `scripts/routing-v4.py`: Budget V4, State V9, Result V6 and
Sample V4. Never mix V4 and V3 units, states, results or observations. Existing tasks
do not automatically migrate.

Independent context is not system read-only. A writable parent without sandbox-denial evidence supports only `logical-readonly`. Review evidence never authorizes modification, commit, push, deployment, restart, or production operation.

## Controlled-Evolution Boundary

This Skill produces independent-review evidence and attribution input; it does not maintain the cross-task evolution contract. Route long-window Reviewer yield, model-cost, or routing-deviation governance to `controlled-evolution-governance`. A single review must not load evolution rules automatically.
