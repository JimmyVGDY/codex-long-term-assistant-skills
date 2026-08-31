# Reviewer Scope and Cost Tiers

Cost tiers control reviewer count, reading scope, and maximum workload. They do not directly define execution workflow or model reasoning effort. See `reviewer-model-routing.md` for models.

| Tier | Applicable Scope | Default Reviewers | Context Principle |
|---|---|---:|---|
| `economy` | Local, low-risk, well-evidenced, or one mechanical verification dimension | 0–1 | Read summary, diff statistics, and target hunks only; do not expand the call chain |
| `balanced` | Ordinary changes to core behavior | 1–2 | Complete context for changed files and direct neighbors, partitioned by responsibility |
| `deep` | Security, migration, core state, cross-service, or production risk | 2–3 | Permit critical call chains and one conflict adjudication, but still prohibit unbounded repository scans |

## Selection Rules

- A small task with direct targeted tests and coordinating-agent self-review may use no subreviewer.
- Every reviewer needs a unique responsibility. Merge or remove overlapping roles instead of adding people.
- `deep` uses `terra-medium` by default and upgrades only one critical dimension that meets high-risk conditions to `terra-high`.
- Round two rereviews only dimensions affected by centralized repairs and normally uses at most two reviewers. Round three is not a default flow; after explicit hard-limit relaxation, it may use one reviewer for one blocking adjudication.
- A subagent receives only the minimum review packet and returns structured findings, checked scope, unverified items, and model runtime evidence.
- Cost tiers cannot lower evidence standards. Insufficient evidence produces an unverified result, not false certainty.
