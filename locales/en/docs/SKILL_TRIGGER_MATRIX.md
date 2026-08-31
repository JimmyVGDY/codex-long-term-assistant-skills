# Skill Automatic Trigger and Composition Matrix (v3.3)

## 0. Minimum Sufficient Loading

```text
PRIMARY_DOMAIN_SKILL_LIMIT = 1
DEFAULT_SUPPORTING_SKILL_LIMIT = 2
MAX_ACTIVE_SKILLS_WITHOUT_JUSTIFICATION = 4
```

1. Select one primary domain Skill for each phase.
2. Add at most two supporting Skills by default.
3. Activate workflow Skills by phase; do not preload every delivery, review, documentation, and memory rule during initial analysis.
4. More than four active Skills require a unique responsibility for each.
5. Remove Skills from the active set when their phase ends.
6. Explicit requester choices take priority but cannot expand permissions or bypass project rules.

Typical phases:

```text
Analysis: domain or log Skill
-> Design: preimplementation review when needed
-> Implementation: domain + quality delivery
-> Stable diff: postimplementation review
-> Formal report: documentation Skill
-> Cross-session: long-running memory
```

---

## 1. Typical Single-Skill Triggers

| Skill | Should Trigger | Normally Should Not Trigger Alone |
|---|---|---|
| `java-backend-engineering` | “Analyze why this Spring transaction is ineffective.” | A Vue styling adjustment |
| `python-backend-ai-engineering` | “Diagnose blocking in this FastAPI async endpoint.” | A pure Java MyBatis query |
| `frontend-engineering` | “Repair the request race after route navigation.” | Pure database-index analysis |
| `data-middleware-ai-infrastructure` | “Analyze this Redis hot key and cache breakdown.” | Explain an ordinary Java null dereference |
| `log-observability-analysis` | “Analyze these local logs and build a cross-service timeline.” | Refactoring without observability input |
| `engineering-quality-delivery` | “Modify, test, review, and commit locally.” | Explain one concept |
| `multi-agent-independent-review` | “Have several Reviewers comprehensively review the diff and reduce rework.” | Wording without behavior change |
| `technical-document-writing` | “Write a formal architecture design from the repository.” | Change one commit message |
| `long-running-task-memory` | “The task spans days; record each recoverable node.” | A one-session small repair |

## 2. Recommended Combinations

| Task | Recommended Combination |
|---|---|
| Java bug repair | Java + quality delivery; add multi-agent review for medium/high risk |
| Java plus Redis/MQ repair | Java + data infrastructure + quality delivery + multi-agent review |
| Python AI worker incident | Logs + Python + data infrastructure; add quality delivery for modification and review for high risk |
| End-to-end frontend/backend SSE repair | Frontend + Java/Python + data infrastructure + quality delivery + multi-agent review |
| Architecture document from code | Documentation + actual technology Skill |
| Modify code and formal design | Technology + quality delivery + documentation |
| Large cross-session change | Technology + quality delivery + memory; add review after code stabilizes |
| Production deployment runbook | Documentation + data infrastructure + quality delivery |
| Comprehensive read-only review | Multi-agent review + technology Skill |
| Multi-day production observation | Logs + memory + domain; add quality delivery only when switching to writes |

## 3. Log-Analysis Trigger Tests

### Should Trigger

1. Analyze multiple application logs and compressed archives in a local directory.
2. Build an incident timeline from Docker, Kubernetes pod, and Nginx logs.
3. Read-only analysis of production Java service, connection-pool, and RabbitMQ logs.
4. Correlate services by trace ID and distinguish root cause from symptoms.
5. Cluster exceptions, count frequency, and propose validation steps.

### Normally Should Not Trigger

1. Pure code design with no observability data.
2. README punctuation only.
3. A new business feature without incident evidence.
4. A theoretical concept unrelated to current logs.

### Mode Selection

- Local static files: bounded decompression and temporary parsing, without overwriting originals.
- Local runtime: read-only by default; restart and modification separately authorized.
- Remote nonproduction: bounded command cost and no assumed write permission.
- Production read-only: bounded time, lines, and query cost; no cleaning, restart, deployment, or writes.

## 4. Multi-Agent Review Trigger Tests

### Should Trigger

1. The diff affects authorization, public APIs, databases, and historical data; run comprehensive multi-agent review.
2. After repair, independently check function, regression, security, performance, data, and concurrency.
3. Find issues once, attribute consistently, and repair centrally to reduce rework.
4. The diff crosses backend, frontend, and messaging and benefits from parallel read-only review.
5. A data migration is about to be committed and requires strict independent review.

### Normally Should Not Trigger

1. Markdown punctuation only.
2. Explain an exception without changing code.
3. Split existing commits without file changes.
4. One local self-check explicitly requested for a low-risk nonbehavioral change.

### Selection Rules

- Low risk: 0–1 Reviewer, normally `economy` and Luna.
- Medium risk: 1–2 Reviewers, normally `balanced`.
- High risk: 2–3 Reviewers, normally `deep`; only a critical dimension may use Terra High.
- Do not add duplicate responsibilities to meet a count.
- Do not modify before every first-round result returns.
- Defaults: parallel 3, total 6, two post rounds, two repair rounds, one Terra High; budget model, people, context, and rounds together.

## 5. Long-Running Memory Trigger Tests

### Should Trigger

1. Work will span sessions or days.
2. The task requires updating task and progress documents after each small node.
3. Multiple agents work in parallel and context compaction must remain recoverable.
4. A production rollout requires continuous observation and recorded validation state.
5. The conversation is long with multiple implementation phases remaining.

### Small-Node Checkpoints

Update `CURRENT_TASK.md` and `PROGRESS.md` after:

- forming a call-chain conclusion;
- confirming or excluding a root cause;
- completing one functional-boundary change;
- completing a build, test, migration, or sample validation;
- dispatching, collecting, or consolidating one Reviewer round;
- completing centralized repair or targeted rereview;
- a blocker, scope change, commit, deployment, or pause.

One `ls`, `grep`, inconclusive read, or immediately reverted experiment does not need a checkpoint.

## 6. Documentation Skill Trigger Tests

### Should Trigger Implicitly

1. Write a system architecture design from the current repository.
2. Restructure an existing Markdown technical proposal while preserving business definitions.
3. Produce a database schema and index design.
4. Write an incident analysis from logs and source.
5. Prepare a formal management discussion report.
6. Write deployment, staged-rollout, and rollback operations.
7. Write API design and error-code documentation.

### Normally Should Not Trigger Alone

1. Add one comment to a Java method.
2. Change a commit message to Chinese.
3. Update one CHANGELOG entry.
4. Explain Redis cache breakdown.
5. Run `npm run build` and report the result.

## 7. Real Codex Routing Regression

Package resources:

- `tests/skill-routing-cases.json`: required, optional, forbidden, and maximum active Skills;
- `scripts/routing-eval.py`: schema validation, observation templates, and scoring.

Usage:

```bash
python3 scripts/routing-eval.py validate
python3 scripts/routing-eval.py make-template --output routing-observations.json
```

Send each test prompt in Codex and record the actual displayed or reported Skills; never fill results from expectations. Then:

```bash
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

Package validation proves the cases and tool are valid, not that local Codex activated them. Rerun after changing a Skill name, description, global routing rule, or composition boundary.

## Reviewer Isolation Scheduling

- TOML `read-only` expresses configuration intent only.
- A `danger-full-access` or `workspace-write` parent normally permits only `logical-readonly` claims.
- High-risk, production, and strict read-only tasks require an entirely read-only parent or valid system-isolation evidence.
- Self-review is not an independent Reviewer; logical read-only is not system isolation.

## V4.1 General Frontend Routing

| Scenario | Primary Skill | Supporting Skill |
|---|---|---|
| Vue/Nuxt, React/Next/Remix, Preact, Angular, Svelte, Astro/Ember, or legacy/static pages | `frontend-engineering` | Quality delivery when modifying |
| Server logic in SSR/full-stack frontend | `frontend-engineering` | Relevant backend and data infrastructure |
| Microfrontend/monorepo | `frontend-engineering` | Quality/documentation according to the change |
| Hybrid Web, WebView, or renderer | `frontend-engineering` | Review native bridge, main process, and system capability separately |
| Electron/Tauri main process or native mobile | Do not use `frontend-engineering` | Choose system/backend/security capabilities |
| Pure Node.js backend API/worker | Do not use `frontend-engineering` | Backend/data Skill |
