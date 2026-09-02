# Mapping Source Rules to Codex V7.2 Resources

| Rule or Capability | Codex V5.0 Target |
|---|---|
| Global cross-project boundaries, authorization, and model routing | `global/AGENTS.md` |
| General backend, including Java/Python/Node.js/Go/.NET/Rust guidance | `skills/backend-engineering/` |
| General frontend engineering | `skills/frontend-engineering/` |
| General AI engineering | `skills/ai-engineering/` |
| Data, middleware, and infrastructure | `skills/data-middleware-infrastructure/` |
| Logs and observability | `skills/log-observability-analysis/` |
| Engineering quality, execution envelopes, and evidence fingerprints | `skills/engineering-quality-delivery/` |
| Technical documentation and formal reports | `skills/technical-document-writing/` |
| Long-term memory, checkpoint deduplication, and recovery | `skills/long-running-task-memory/` |
| Multi-agent independent review | `skills/multi-agent-independent-review/` |
| Luna/Terra model policy | `docs/MODEL_ROUTING_AND_COST_POLICY.md` |
| Codex `[agents]` configuration | `config/agents.example.toml`, `docs/CODEX_CONFIG_GUIDE.md` |
| Seven narrow Reviewers | `custom-agents/*.toml` |
| Reviewer model routing | `skills/multi-agent-independent-review/references/reviewer-model-routing.md` |
| Review packet and freshness | `skills/multi-agent-independent-review/scripts/review_packet.py` |
| Budgets, duplicate dispatch, and model audit | `skills/multi-agent-independent-review/scripts/review_controller.py` |
| Checkpoint-content deduplication | `skills/long-running-task-memory/scripts/checkpoint.py` |
| Routing regression | `tests/skill-routing-cases.json`, `scripts/routing-eval.py` |
| Package structure, semantics, and isolated-install validation | `scripts/validate-package.py`, `scripts/semantic-lint.py` |

## Responsibility Boundaries

- `LIGHT/STANDARD/STRICT` govern execution and delivery gates.
- `economy/balanced/deep` govern Reviewer count and context budget.
- Four model tiers govern model and reasoning effort for one subagent.
- The main agent is the sole coordinator and shared-memory writer.
- Reviewers have narrow responsibilities, read progressively, and return structured results.
- `sandbox_mode = "read-only"` is not proof of runtime system isolation.

`SKILL.md` retains triggers, mandatory entry points, cost boundaries, and composition. Detailed rules belong in `references/`, templates in `assets/`, and executable guardrails in `scripts/`.
