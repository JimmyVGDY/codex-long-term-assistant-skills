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
7. Reviewer, Explorer, and Worker share one root-task budget and automatic routing stops at Terra High. Runtime model status remains `UNAVAILABLE` unless a trusted host attestation is correlated to the Hook event.

```text
Lifecycle Hooks -> TaskOutcomeEvent V3 -> task aggregation
-> project isolation -> Snapshot -> Assessment -> Proposal
-> human decision -> separate implementation task -> normal validation and delivery gates
```

Use Luna for mechanical aggregation and Terra only for material cross-task conflicts or high-risk policy decisions. Higher model effort cannot repair poor evidence quality.

DelegationBudget calibration consumes only parent-finalized, project-bound samples with approved-profile attribution and cost-basis units. Insufficient adjacent-tier samples require no change, and every proposal retains `execution_authorization=NONE`.
