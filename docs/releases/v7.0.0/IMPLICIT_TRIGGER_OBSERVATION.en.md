# V7.0.0 Real Implicit-Trigger Observation

Chinese: [IMPLICIT_TRIGGER_OBSERVATION.md](IMPLICIT_TRIGGER_OBSERVATION.md)

Observation date: 2026-09-01

Scope: Codex CLI 0.150.1, `gpt-5.6-luna`, `low` reasoning effort, and four read-only scenarios.

## Conclusion

All four representative scenarios selected the expected domain routing without explicitly naming the target Skill. A later complete Plugin upgrade also selected the general backend and data-infrastructure routes in a fresh read-only task. The real implicit-trigger observation is PASS. This result covers only the scenarios in this report and does not establish deterministic selection for every natural-language variation.

## Method

1. Confirmed that the four target directories did not exist under `$HOME/.agents/skills` before installation.
2. Temporarily copied only `$backend-engineering`, `$ai-engineering`, `$frontend-engineering`, and `$data-middleware-infrastructure`; no AGENTS, Hooks, Reviewers, or other Skills were installed.
3. Ran four independent read-only tasks in a clean temporary Git repository with no repository-scoped Skills, using `--ephemeral --ignore-user-config --ignore-rules`.
4. Each prompt described an engineering scenario without naming the Skill that should be selected, then requested a final report of the Skills actually used.
5. Removed the four user-level directories after observation and read back that they and all observation directories were absent.

## Results

| Scenario | Expected routing | Reported selection | Result |
| --- | --- | --- | --- |
| Node.js order state, PostgreSQL transaction, RabbitMQ, idempotency, and compatibility | Backend + data infrastructure | `backend-engineering,data-middleware-infrastructure` | PASS |
| Language-neutral RAG, structured output, citations, evaluation, and hallucination control | AI | `ai-engineering` | PASS |
| Multimodal inference worker, GPU quotas, queue backpressure, object storage, and evaluation | AI + data infrastructure | `ai-engineering,data-middleware-infrastructure` | PASS |
| React multistep form, accessibility, responsive layout, and client state recovery | Frontend | `frontend-engineering` | PASS |

## Complete Plugin upgrade readback

- Managed 6.6.0 to 7.0.0 upgrade on native Windows Codex CLI 0.150.1: PASS.
- Codex CLI readback of `installed=true`, `enabled=true`, and `version=7.0.0`: PASS.
- Source, Marketplace, and Plugin cache each contain 182 payload files with the same digest: PASS.
- Ten Skills, seven Reviewers, six Hooks, and exactly one managed AGENTS marker pair: PASS.
- The `config.toml` SHA-256 stayed unchanged, all 34 existing third-party user Skills remained, and all four Manifest-declared legacy Skills were absent: PASS.
- A fresh read-only Codex task reported `backend-engineering,data-middleware-infrastructure`: PASS.

## Evidence boundaries

- Earlier repository-scoped `.agents/skills` attempts did not load V7 Skills because the host denied access. Their `NONE` or other-Skill results remain invalid and are excluded from PASS.
- The initial four-scenario PASS is based on loading from the standard user-level Skill directory and each task's final `ACTIVATED_SKILLS` report. The fresh task after the complete Plugin upgrade provides a second host-evidence layer. Neither is an independent low-level router trace.
- Commands selected `gpt-5.6-luna` with `low` effort, but no external provider trace independently established the actual model.
- The complete Plugin acceptance used the current source tree, not a future public Release ZIP. Public artifacts still require independent provenance and post-download acceptance.
- Git commit, push, public publication, restart, and production writes are not established by this report and require separate action readback.
- Restoration readback confirmed that the four temporary user-level Skill directories, both repository observation directories, and the known system temporary observation directory were absent.
