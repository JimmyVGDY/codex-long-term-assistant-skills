---
name: controlled-evolution-governance
description: Use only for cross-task retrospectives, observation governance, model-cost routing, reviewer calibration, routing drift, proposal lifecycle, project isolation, and assistant version governance.
---

# Controlled Evolution Governance

1. Operate only on structured observation facts, statistics, evidence references, assessments, and proposals.
2. Every proposal keeps `execution_authorization=NONE`.
3. `ACCEPT` permits creation of a separate implementation task. It does not grant file, Git, deployment, production, or data-write authority.
4. Aggregate only exact `project_id + repo_fingerprint` matches. Deduplicate by `event_id`, then aggregate by `task_id`.
5. Terminal outcomes are only `PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN`; generic status fields cannot infer outcome.
6. Hooks retain minimal structured metadata and never raw prompts, full answers, source bodies, patches, tokens, cookies, API keys, or credentials.
7. Reviewers, explorers and workers share one root budget. New tasks use script-controlled GPT-6 defaults and bounded adjustments; old roots replay their frozen policy. Missing calibration data does not prevent default delegation. Automatic xhigh/max/ultra remain forbidden. Never read, infer, store, or export host model identity.
8. Pass the health gate before analysis. Project automation requires explicit opt-in. Keep NO_CHANGE, WAITING_FOR_TASKS and COOLDOWN quiet; report only meaningful changes, new candidates or actionable failures.
9. New proposals freeze testable hypotheses. Separate implementation validation from benefit proof and revalidate references, windows, independent samples and quality guardrails on replay. Confirmed causes generate pending regression candidates without automatic implementation or cross-project promotion.

```text
Lifecycle Hooks -> TaskOutcomeEvent V3 -> task aggregation
-> project isolation -> Snapshot -> Assessment -> Proposal
-> human decision -> separate implementation task -> normal validation and delivery gates
```

Keep the main agent's selection. For subagents, follow [script decisions and bounded flexibility](../multi-agent-independent-review/references/script-first-routing.md) and execute the returned exact parameters. The default pool contains GPT-6 Luna, Sol and Astra at low/medium/high; unknown work uses Sol/medium without requiring qualification, gain cards or a long justification. Models may propose semantic adjustments, but scripts recalculate them within the existing authorization and root budget. Missing evidence selects a default or degraded path and never becomes a fabricated PASS.

Scripts aggregate, deduplicate and compute windows and costs. Models retain semantic judgment. Insufficient samples leave policy parameters unchanged while normal default delegation continues; stronger models cannot repair corrupted evidence.

DelegationBudget calibration consumes only parent-finalized, project-bound samples with approved-profile attribution and cost-basis units. Insufficient adjacent-tier samples require no change, and every proposal retains `execution_authorization=NONE`.
