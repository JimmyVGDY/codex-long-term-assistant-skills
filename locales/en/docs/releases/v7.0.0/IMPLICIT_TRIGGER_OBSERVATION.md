# V7.0.0 Real Implicit-Trigger Observation

Observation date: 2026-09-01

Codex CLI 0.150.1 ran four independent read-only scenarios with `gpt-5.6-luna` and `low` effort. The prompts described the engineering work without explicitly naming the expected Skill.

| Scenario | Reported selection | Result |
| --- | --- | --- |
| Node.js backend with PostgreSQL and RabbitMQ | `backend-engineering,data-middleware-infrastructure` | PASS |
| Language-neutral RAG and evaluation | `ai-engineering` | PASS |
| Multimodal GPU worker and queue infrastructure | `ai-engineering,data-middleware-infrastructure` | PASS |
| React browser UI | `frontend-engineering` | PASS |

Only the four V7 domain Skills were temporarily copied to `$HOME/.agents/skills`. They did not exist before the observation and were removed afterward; readback also confirmed that all observation directories were absent. No AGENTS, Hooks, Reviewers, other Skills, Plugin registration, commit, push, publication, deployment, restart, or production write was changed.

A later complete source-tree Plugin upgrade from 6.6.0 to 7.0.0 also passed: Codex reported installed and enabled 7.0.0; source, Marketplace, and cache matched at 182 payload files; ten Skills, seven Reviewers, and six Hooks were present; `config.toml` stayed unchanged; 34 third-party user Skills remained; and a fresh task selected `backend-engineering,data-middleware-infrastructure`.

This PASS is based on task-reported routing and host readback, not an independent low-level router trace. Earlier repository-scoped attempts that failed Skill scanning remain invalid and are excluded. The complete Plugin acceptance used the source tree, not a public Release ZIP.
