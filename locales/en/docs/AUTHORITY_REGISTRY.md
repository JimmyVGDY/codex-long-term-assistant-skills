# Current Authoritative Source Registry

> Status: `active`. The files below are the current fact owners; the version that first introduced them does not limit their current scope.

## 1. Principle

Each fact has one authoritative owner. Other files may reference or project it but cannot become a second overwritable version.

| Fact | Sole Owner | Allowed Projections |
|---|---|---|
| Package version, Skills, Reviewers, and limits | `manifest.json` | README, Skill Matrix, validation reports |
| Project identity and stable boundaries | `project-profile.json` | Onboarding report, envelope references |
| Current project phase and baseline | `project-state.json` | State summary |
| Task phase, gates, evidence, and actions | `execution-state.json` | Finalization report, handoff |
| Reviewer rounds, findings, and review state | `review-state.json` | Review ledger |
| Root-task budget, permits, and reservations | External DelegationBudget V2 ledger managed by `scripts/delegation-budget.py` | Envelope references, cost summary |
| Hook registration | `hooks/hooks.json` | Configuration guide, architecture |
| Worktree capability locations and coverage | Profile-adjacent `capability-index/<worktree_id>` managed by CapabilityStore | Query results, decision references |
| Project gate opt-in and binding | Account-external `capability-gates/<worktree_id>.json` managed by GatePolicy | Status readback |
| Legacy gate task state and current receipts | Profile-adjacent `capability-gate/<worktree_id>` managed by GateTask/Workflow | Prepare/finish/check results; in V7.6.2 these are legacy state facts only and do not grant native-write permission |
| Frozen review input | Review Packet `manifest.json` | Packet summary |
| Current task recovery | `CURRENT_TASK.md` + `PROGRESS.md` | Recovery summary |
| Long-lived project facts | `project-memory.md` | Project-document references |
| Cross-project experience candidate | Knowledge Candidate JSON | Human evaluation report |

## 2. State Conflicts

- Machine state versus Markdown: prefer machine state and record the conflict.
- Project documentation versus actual Git/runtime results: prefer currently verifiable facts.
- Checkpoint versus Project Memory: a checkpoint describes task state at that time and cannot overwrite reviewed project facts.
- Knowledge Candidate versus current project facts: the candidate is input only and cannot be applied automatically.
- Approval versus Evidence: they have different responsibilities and cannot replace each other.

## 3. Document State

Recommended labels:

- `active`: currently applicable specification;
- `reference`: read on demand;
- `historical`: traceability only;
- `generated`: projected from machine state and regenerable.

Historical documents do not override active rules. Generated documents must not become manually maintained independent sources of truth.

## Machine source references

- <!-- cp-fact:owner.budget -->repository-external DelegationBudget V2 JSONL via delegation-budget.py<!-- /cp-fact -->
- <!-- cp-fact:owner.review -->review-state.json via review_controller.py<!-- /cp-fact -->
