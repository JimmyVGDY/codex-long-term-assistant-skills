# V7.4 Current Authoritative Source Registry

> Status: `active`. The files below are the current fact owners; the version that first introduced them does not limit their current scope.

## 1. Principle

Each fact has one authoritative owner. Other files may reference or project it but cannot become a second overwritable version.

| Fact | Sole Owner | Allowed Projections |
|---|---|---|
| Package version, Skills, Reviewers, and limits | `manifest.json` | README, Skill Matrix, validation reports |
| Project identity and stable boundaries | `project-profile.json` | Onboarding report, envelope references |
| Current project phase and baseline | `project-state.json` | State summary |
| Task phase, gates, evidence, and actions | `execution-state.json` | Finalization report, handoff |
| Reviewer scheduling and budget | `review-state.json` | Review ledger |
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
