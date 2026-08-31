# Execution Profiles and Phase State Machine

## 1. Three Execution Profiles

| Profile | Typical Work | Default Skills and Gates |
|---|---|---|
| `LIGHT` | Concept explanation, one-time read-only analysis, wording without behavioral change, or a tiny low-risk change | One primary domain skill; no long-term memory; no mechanical multi-agent review; validation proportional to the actual change |
| `STANDARD` | Ordinary bug repair, API/page adjustment, or behavioral script/configuration change | One domain skill plus quality delivery; minimum targeted validation; 0–2 reviewers by risk; simplified envelope when needed |
| `STRICT` | Production, real data, authorization security, money/inventory, irreversible migration, core state machines, or high-risk cross-service change | Long-term memory, complete envelope, preimplementation review, minimum validation, independent postreview, rollback and stopping conditions; actual isolation evidence for strict read-only claims |

### Escalation and Deescalation

- Escalate when real data, irreversible change, public contracts, cross-service scope, authorization, or high-resource risk appears.
- Once in `STRICT`, do not deescalate automatically to save time. Record reason, explicit authorization, and retained risk.
- Availability of multi-agent or long-term-memory features does not require them for every task.

## 2. Phase State Machine

Standard phases:

```text
IDENTIFY -> PLAN -> IMPLEMENT -> VALIDATE -> REVIEW -> DELIVER -> CLOSED
```

Auxiliary states: `BLOCKED`, `CANCELLED`, `ROLLBACK`, `RECOVER`.

### Phase Responsibilities

- `IDENTIFY`: identify project, facts, goals, permissions, and risks; do not expand directly into modification.
- `PLAN`: define scope, non-goals, design, gates, rollback, and skill activation.
- `IMPLEMENT`: change only the current functional boundary; reviewers do not modify code here.
- `VALIDATE`: run builds, targeted tests, samples, migration checks, or runtime checks and record fingerprints.
- `REVIEW`: independent-context reviewers work from one packet; do not modify before collecting the round.
- `DELIVER`: check Git, documentation, authorization, commit/push/deploy/restart, and effective state.
- `RECOVER`: after compaction or switching, reconcile envelope, checkpoints, Git, and evidence freshness.

### Transition Gates

- `PLAN -> IMPLEMENT`: goals, scope, authorization, and stopping conditions are explicit; STRICT preimplementation gates passed.
- `IMPLEMENT -> VALIDATE`: diff is stable and contains no obvious unrelated changes.
- `VALIDATE -> REVIEW`: minimum validation has real evidence; failures and unverified items are recorded.
- `REVIEW -> DELIVER`: blocking issues are resolved and affected evidence remains current.
- Any phase may enter `BLOCKED` or return to an earlier phase when scope expands, permissions are insufficient, production risk appears, or evidence becomes stale.
