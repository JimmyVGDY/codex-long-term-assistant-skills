# On-Demand Controlled Evolution Reference

This Skill invokes the shared Evolution Runtime only after an explicit trigger. It does not maintain a second contract.

Authoritative references:

- `runtime/cp_runtime/evolution/manifest.json`
- `docs/evolution/SELF_EVOLUTION_ARCHITECTURE.md`
- `docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md`

Mandatory boundaries:

1. Run a dry-run first.
2. Do not create a Proposal from insufficient data.
3. Proposal execution authorization must remain NONE.
4. ACCEPT records only a human decision.
5. Implementation requires a separate Task and fresh approval.
6. Never modify or delete a Skill, Reviewer, model configuration, or business code automatically.
7. Fail closed when JSONL or the hash chain is damaged.
