# Codex Cross-Project Long-Term Engineering Assistant V6.5 User Guide

## 1. Intended Use

V6.5 supports long-term maintenance across multiple software projects. It is suitable for:

- evidence-based conclusions after reading existing code, configuration, logs, and tests;
- Java, Python, frontend, data, middleware, and AI-infrastructure changes;
- explicit authorization boundaries between modification, validation, review, commit, push, deployment, and rollback;
- maintaining objectives, plans, evidence, risks, and checkpoints across sessions;
- independent review of functionality, compatibility, security, performance, data contracts, state/concurrency, and delivery evidence; and
- cross-task review and controlled optimization proposals from minimal lifecycle events.

Ordinary tasks require no extra initialization after installation. Open a new Codex task in the target repository and state the objective, scope, and authorization.

## 2. Confirm Installation State

```powershell
codex --version
codex plugin list --json
```

Expected state:

```text
codex-cli 0.150.1
plugin id = codex-cross-project-engineering-assistant@cp-assistant-local
installed = true
enabled = true
version = 6.5.0
```

Re-run verification with:

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
```

Tasks opened before the upgrade may retain the previous Plugin snapshot. Use a new task after upgrading for final Skill, reviewer, and Hook discovery tests.

## 3. Minimum Usage

Ordinary read-only analysis:

```text
Inspect the exception-handling paths in the current project.
Read the relevant code, configuration, and tests first. Analyze only; do not modify files.
Report the root cause, evidence, risk, and smallest recommended repair.
```

Implement a repair:

```text
Fix duplicate order submissions.
First confirm the call chain, data boundary, and current baseline, then implement the minimum
sufficient change. Complete targeted tests and necessary regression checks, then arrange independent
review according to risk. Do not commit, push, deploy, or restart.
```

State the delivery boundary explicitly:

```text
Complete implementation, tests, and independent review, then commit to local Git.
Do not push, deploy, or restart. In the final report, state modification, validation, review,
commit, push, deployment, restart, and effective-runtime status separately.
```

The package selects the minimum sufficient Skills for the technology stack. It does not load every available Skill at once.

## 3.1 V6.5 Integrity Keyring and Event Seals

Initialization creates only a missing keyring and never overwrites existing keys:

```powershell
python scripts\integrity-key.py init
python scripts\integrity-key.py status
python scripts\integrity-key.py verify
```

Create and verify a seal for the current TaskOutcomeEvent V2 chain head:

```powershell
python scripts\event-seal.py create --event-file <task-outcome-v2.jsonl>
python scripts\event-seal.py verify --event-file <task-outcome-v2.jsonl>
```

Rotate the event key with:

```powershell
python scripts\integrity-key.py rotate --purpose event-hmac
```

The old key becomes `RETIRED` and continues to verify historical seals; only the `ACTIVE` key signs new seals. `SEALED_CURRENT` means the current chain head is sealed. `VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL` means the historical sealed prefix remains valid and legitimate events were appended afterward; run `create` again to seal the new head.

Host-session JSONL is used only as diagnostic model evidence and for conflict detection. Even complete field correlation cannot promote it to trusted Hook model evidence. Release validation separates two facts: a real lifecycle test proves that a reviewer started and stopped, while a model-gate report from direct calls to the installed PreToolUse Hook proves the Luna Low -> Luna Medium -> Terra Medium -> Terra High route, the Terra High ceiling, and rejection of Sol and xhigh. Both gates must pass for release acceptance.

## 3.2 Reviewer Calibration

`reviewer_stats` in a self-observation snapshot provides:

- stable `result_id` deduplication and conflict counts;
- independent-task count, attribution coverage, and labeled finding count;
- adoption rate with a Wilson 95% interval;
- duration per invocation, cost per adoption or repair, and benefit proxies; and
- `INSUFFICIENT_DATA`, `OBSERVE`, `EFFECTIVE`, `HIGH_DUPLICATION`, `LOW_YIELD_CANDIDATE`, or `CONFLICT` state.

Calibration creates observations and Proposal candidates only. It never disables a reviewer automatically, changes model routing, or grants execution authority.

## 4. The 10 Skills

| Skill | Primary use |
|---|---|
| `java-backend-engineering` | Java, Spring, JVM, Maven, transactions, concurrency, and SSE |
| `python-backend-ai-engineering` | Python, FastAPI, Django, Flask, async I/O, Celery, AI/RAG, and GPU workers |
| `frontend-engineering` | JavaScript, TypeScript, React, Vue, Angular, Svelte, browsers, and renderers |
| `data-middleware-ai-infrastructure` | SQL, Redis, messaging, Elasticsearch, storage, GPU, Docker, Kubernetes, and networking |
| `log-observability-analysis` | Logs, metrics, traces, profiling, alerts, and change events |
| `engineering-quality-delivery` | Modification, tests, Git, release, rollback, approval, and final delivery |
| `multi-agent-independent-review` | Pre-implementation review for high-risk changes and independent review after behavior changes |
| `technical-document-writing` | Technical solutions, architecture, APIs, deployment, incidents, and formal reports |
| `long-running-task-memory` | Cross-session, multi-stage, multi-module, multi-agent, and context-compaction work |
| `controlled-evolution-governance` | Cross-task review, self-observation, cost routing, reviewer value, and Proposal governance |

Select a Skill explicitly when useful:

```text
Use $python-backend-ai-engineering to inspect concurrency in this FastAPI service.
Analyze first; do not modify anything.
```

Each phase normally uses one primary domain Skill plus only the necessary quality, log, review, documentation, or long-running-task support.

## 5. The 7 Reviewers

| Reviewer | Review boundary |
|---|---|
| `cp_review_functional_business` | Functional correctness and business definitions |
| `cp_review_compatibility_regression` | Existing APIs, historical data, regression, and compatibility |
| `cp_review_security_access` | Authentication, authorization, privilege escalation, injection, and sensitive data |
| `cp_review_performance_resources` | SQL, I/O, connections, threads, queues, and resource load |
| `cp_review_data_contract` | Databases, APIs, Redis, messaging, serialization, and consistency boundaries |
| `cp_review_state_concurrency` | Races, idempotency, timeouts, retries, cancellation, and state boundaries |
| `cp_review_test_delivery` | Test evidence, failures, documentation, and delivery boundaries |

Automatic selection example:

```text
After the repair, select only the independent reviewers justified by actual risk and conduct a
logical-read-only review. Do not start all reviewers merely for formality.
```

Explicit selection example:

```text
Start cp_review_security_access with Luna Low.
Inspect authorization, privilege escalation, and sensitive-data risk only. Do not modify files.
```

Reviewer TOML files do not pin models. The automatic cost route is:

```text
Luna Low -> Luna Medium -> Terra Medium -> Terra High
```

Automated work is capped at `gpt-5.6-terra + high`. The PreToolUse Hook rejects explicit Sol, Terra xhigh, max, ultra, unknown models, and any automated dispatch that cannot be proven to stay within the ceiling.

## 6. Long-Running Tasks

Enable long-running-task memory explicitly for cross-session, multi-stage, multi-module, or multi-agent work:

```text
This is a long-running task.
Use $long-running-task-memory to maintain the objective, plan, authorization, evidence, risks,
and checkpoints. Write a checkpoint after every independently recoverable phase and continue until
all acceptance criteria are complete.
```

Typical control files:

```text
CURRENT_TASK.md
PLAN.md
PROGRESS.md
```

Recovery example:

```text
Resume the previous long-running task. Read the current task, plan phase, and three most recent
checkpoints, then verify current Git, source, configuration, and runtime state before continuing.
```

Checkpoints preserve verifiable facts, evidence, authorization, risks, and next actions. They are not automatically promoted to project memory or cross-project knowledge.

## 7. Lifecycle Records

The six Hooks map to these events:

```text
UserPromptSubmit -> TURN_OPENED
PreToolUse       -> PRE_TOOL_GUARD
SubagentStart    -> SUBAGENT_STARTED
SubagentStop     -> SUBAGENT_STOPPED
Stop             -> TASK_COMPLETED
SessionEnd       -> SESSION_ENDED
```

TaskOutcomeEvent 2.0 stores minimal structured metadata:

- event, session, turn, and task references;
- `project_id + repo_fingerprint`;
- actual model and reasoning effort only when supplied explicitly by trusted host fields;
- reviewer, finding, and repair-round counts;
- an explicit terminal result, or `UNKNOWN` when absent;
- a forward SHA-256 chain with optional HMAC; and
- fact-source fields that distinguish explicit host values from unavailable evidence.

V6.5 writes events into continuous segments. Missing cross-segment links, sequence errors, damaged hashes, or invalid schemas fail closed. If interruption leaves a partial active tail record, it is moved to a timestamped audit file while the complete chain is preserved.

Raw prompts, full responses, source text, diffs, patches, tokens, cookies, API keys, and credentials are not stored by default. Historical events that did not exist before installation are never fabricated retroactively.

## 8. Cross-Project Isolation

Every project binds both:

```text
project_id
repo_fingerprint
```

Aggregation, Snapshot, Assessment, and Proposal may use records only when both values match. Any mismatch stops cross-task aggregation so another project's schema, APIs, credentials, business definitions, or observations cannot enter the current project.

## 9. Review and Controlled Evolution

Example review prompt:

```text
Use $controlled-evolution-governance to analyze recent Event, Checkpoint, Review, and Evidence records
for the current project. Generate a Snapshot, Assessment, and Optimization Proposal.
Generate proposals only; do not accept or implement them.
```

Standard chain:

```text
Lifecycle Event
  -> Task aggregation
  -> Snapshot
  -> Assessment
  -> Optimization Proposal
  -> human ACCEPT / REJECT / DEFER
  -> separate implementation task after ACCEPT
  -> independent validation and Proposal closure
```

Lifecycle Hooks automatically record minimal prerequisite metadata. Long-running-task memory maintains objectives, plans, authorization, key decisions, and validation evidence at recoverable points. Missing or insufficiently supported information must remain `UNKNOWN`, be listed as a gap, or stop Proposal generation; it must never be guessed.

`execution_authorization=NONE` is permanent. `ACCEPT` endorses a direction only; it does not authorize file modification, commit, push, deployment, restart, or production operations.

## 10. Security and Authorization

These actions always remain separate boundaries:

- read-only analysis;
- local file modification;
- tests or real external calls;
- Git commit;
- Git push;
- deployment;
- restart;
- data modification; and
- production operations.

Passing tests proves behavior only within the tested scope and grants no other authorization. Final reports must state modification, static checks, runtime validation, independent review, commit, push, deployment, restart, and effective-runtime status separately.

## 11. Common Problems

### Plugin Files Exist but the Plugin Is Disabled

Treat `codex plugin list --json` as authoritative. Re-run the installer and `verify`; file presence alone does not prove registration.

### Windows Hook Cannot Find Python

V6.5 does not require a separate `python3.exe`. Confirm that account-level CPython, `python.exe`, or `py.exe -3` is available and that the Hook starts through `cp_hook.cmd`.

### Events Do Not Enter Aggregation

Confirm that both `project_id` and `repo_fingerprint` match. Then verify segment continuity, hash integrity, and schema version 2.0.

### Insufficient Review Data

Use existing Git, logs, tests, checkpoints, and Evidence. Keep gaps unverified. Enable long-running-task memory for future work; do not backfill facts that never existed.

### Interrupted Installation

```powershell
python scripts\package_manager.py status --scope user --mode plugin --json
python scripts\package_manager.py doctor --recover
```

Do not recursively delete the entire `.codex`, `.agents`, or plugins directory. Preserve logs and stop before overwriting when unknown content or ownership conflicts are detected.

## 12. Acceptance Checklist

- [ ] Codex is 0.150.1
- [ ] Plugin reports `installed=true`, `enabled=true`, and `version=6.5.0`
- [ ] All 10 Skills are discoverable
- [ ] All 7 reviewers are discoverable and their TOML does not pin a model
- [ ] All 6 Hooks load
- [ ] SessionEnd timeout is 3 seconds
- [ ] Windows Hooks do not require an additional `python3.exe`
- [ ] Primary-agent model configuration is unchanged
- [ ] Historical project context and self-observation data did not decrease
- [ ] Upgrade backup is retained
- [ ] No installation transaction remains active
- [ ] Two official ZIP builds are byte-identical
- [ ] ZIP, Marketplace, and cache payload digests match
- [ ] A new session produces the complete five-event sequence
- [ ] TaskOutcomeEvent schema is 2.0 and its hash chain is continuous
- [ ] Dual `project_id + repo_fingerprint` isolation passes
- [ ] Model gate permits Terra High and rejects Terra xhigh, Sol, and higher automated tiers
- [ ] Host-session model data remains `DIAGNOSTIC` and is not misrepresented as trusted Hook evidence
- [ ] The unified validator and attestation bind all official evidence

For installation and recovery details, see `docs/INSTALLATION_RECOVERY.md`. For version changes, see `docs/releases/v6.5.0/RELEASE_NOTES.md`.
