---
name: multi-agent-independent-review
description: Use for risk-based design gates, independent reviews of behavior changes, or checking system-read-only isolation before review. Exclude routine low-risk self-checks and formatting without behavioral impact; do not dispatch reviewers for formality.
---

# Independent Multi-Agent Review

## Entry and Phase Boundaries

- When checking isolation only, report actual capability and missing evidence without initializing a review. Missing system-isolation proof means logical-readonly, not verified system-read-only. If the user explicitly requires system isolation and the host cannot provide it, restrict that review action while other authorized work continues.
- Retain the relevant primary domain capability when independently reviewing implementation behavior. Review procedure and quality evidence do not replace domain judgment. Keep cross-phase memory only for current recovery or state maintenance, and explain combinations above the default limit.

The execution steps below apply to actual review after its gate is satisfied.

1. Select the execution profile, shared DelegationBudget, Reviewer effort, and model profile independently. Reviewer state does not charge the total budget twice.
2. Read the root policy first. New defaults follow [script decisions and bounded flexibility](references/script-first-routing.md), using the nine GPT-6 profiles and Sol/medium when information is missing, without statistical qualification. All roles execute script-approved parameters; models retain semantic judgment and may request bounded adjustments. Replay or explicitly select old V3/V4 contracts without changing historical charges.
3. Bind every Review Packet to Project ID, Task ID, Git baseline, Task Envelope, packet hash, validation summary, assigned scope, and a matching Reviewer permit in `delegation-budget.py` when unified accounting is active. For scoped review, also use `scripts/scoped_review.py` to fingerprint targets, statically discovered dependencies, configuration, and authority files. Unknown dynamic dependencies are `INCOMPLETE` and permit bounded review of available scope. Relevant changes are `STALE` and refresh affected material. Scoped PASS never means release-wide PASS.
4. Read summary and statistics first, then assigned diff and direct dependencies, then expand only when evidence remains insufficient.
5. Collect one round before deduplication, root-cause clustering, conflict resolution, and centralized repair.
6. After repair, refresh only affected evidence and packet content. Stop repeated review when the packet is unchanged or no new information exists.
7. The new shared ledger computes attempts, concurrency, necessary holds and allowed adjustments; default parallelism is <=3 with at most one active Astra. Bound review and repair by the task budget without adding a qualification study. Legacy controllers retain cumulative <=6 and post/repair rounds <=2. V3 additionally limits Terra High reviewers to one, Sol/Astra attempts to two with one at a time, and Astra High to one. V4 verifies its fixed root resource vector and complete phase allocation. Apply the stricter root-budget and controller limits.

V4 uses the repository-root `scripts/routing-v4.py`: Budget V4, State V9, Result V6 and
Sample V4. Never mix V4 and V3 units, states, results or observations. Existing tasks
do not silently migrate. A same-chat policy handoff preserves old attempts, charges and late-event ownership.

Independent context is not system read-only. A writable parent without sandbox-denial evidence supports only `logical-readonly`. Review evidence never authorizes modification, commit, push, deployment, restart, or production operation.

## Controlled-Evolution Boundary

This Skill produces independent-review evidence and attribution input; it does not maintain the cross-task evolution contract. Route long-window Reviewer yield, model-cost, or routing-deviation governance to `controlled-evolution-governance`. A single review must not load evolution rules automatically.
