# Codex Cross-Project Long-Term Engineering Assistant V6.3 User Guide

## 1. Document Information

- Applicable version: V6.3.0
- Primary target: native Windows Codex CLI 0.150.1
- Recommended installation: account-level Plugin mode
- Intended audience: developers using Codex for multi-stack engineering, independent review, long-running tasks, and controlled evolution

## 2. What This Package Is

V6.3 is neither a standalone desktop application nor a business-project template. It is an engineering workflow package installed into Codex and includes:

- 10 engineering Skills;
- 7 specialist reviewers;
- 6 lifecycle Hooks;
- TaskOutcomeEvent V2 with an event hash chain;
- long-running-task checkpoints and external project memory;
- controlled Evolution Snapshot, Assessment, and Proposal workflows;
- persistent installation transactions, concurrent-install exclusion, crash recovery, and uninstall tooling; and
- real lifecycle acceptance, byte-for-byte deterministic builds, and machine-readable release attestations.

After installation, open projects and describe work in natural language as usual. The agent progressively loads the appropriate Skill for each task; package scripts do not need to be run manually for ordinary work.

## 3. Install or Upgrade from V6.1

### 3.1 Prerequisites

In PowerShell, confirm:

```powershell
codex --version
python --version
```

V6.3 targets Codex `0.150.1`. A native Windows installation path should look like:

```text
C:\Users\<account-name>\.codex
```

If the process inherits `/mnt/c/Users/.../.codex`, the installer converts it to a native Windows drive path. Do not use a WSL-style path as the native Windows installation target.

### 3.2 Extract the Archive

Do not modify or run files inside the ZIP. For example:

```powershell
Expand-Archive -LiteralPath .\Codex-Skills-V6.3.zip -DestinationPath .\Codex-Skills-V6.3-unpacked
Set-Location .\Codex-Skills-V6.3-unpacked\Codex-Skills-V6.3
```

### 3.3 Inspect the Environment

```powershell
python scripts\package_manager.py doctor
```

Confirm that `version` is `6.3.0`, both `target_codex` and actual `codex_version` are 0.150.1, and `codex_home` is a native Windows path.

If `doctor` reports an incomplete transaction, inspect and recover it before retrying installation:

```powershell
python scripts\package_manager.py status --scope user
python scripts\package_manager.py recover --scope user
```

After recovery, run `doctor` and dry-run again.

### 3.4 Dry Run

```powershell
python scripts\package_manager.py install --scope user --mode plugin --dry-run
```

Check whether:

- the current older version is detected;
- a timestamped backup will be created;
- every target remains within `.codex` and the permitted cp-assistant Marketplace scope;
- a Junction, Reparse Point, or symbolic link blocks the operation;
- externally modified managed files have drifted; and
- any unknown file would be overwritten.

A dry run must not create backups, transaction logs, or Plugin registration changes. Once installation begins, only one transaction may operate on the same `CODEX_HOME` at a time.

### 3.5 Perform the Upgrade

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python scripts\package_manager.py install --scope user --mode plugin
```

The installer prepares the Marketplace, reviewers, and global rules, then invokes Codex Plugin and Marketplace commands to complete registration. Copied files alone do not prove that the Plugin is active.

### 3.6 Verify

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

The target Plugin must report:

```text
pluginId = codex-cross-project-engineering-assistant@cp-assistant-local
installed = true
enabled = true
version = 6.3.0
```

After upgrading, close and reopen Codex App, CLI, or IDE tasks that were already open. Windows itself does not need to restart.

Upgrade backups and committed transaction archives are retained by default for audit and recovery.

## 4. Everyday Use

The usual method is to describe the task directly:

```text
Investigate why this project's login API occasionally returns 500.
First analyze the code and logs using read-only access. Confirm the root cause; do not modify code.
```

```text
Fix duplicate order submissions.
First confirm the call chain and data boundary, then implement the smallest repair, run targeted tests,
and select only the independent reviewers justified by risk. Do not commit, push, or deploy.
```

The agent chooses Skills from current source, configuration, logs, tests, and authorization. Installing all capabilities does not cause them all to load together.

## 5. The 10 Skills

| Skill | Applicable work |
|---|---|
| `java-backend-engineering` | Java, Spring, JVM, Maven, transactions, concurrency, and SSE |
| `python-backend-ai-engineering` | Python, FastAPI, Django, Flask, async I/O, Celery, AI/RAG, and GPU workers |
| `frontend-engineering` | JavaScript/TypeScript, React, Vue, Angular, Svelte, browsers, and renderers |
| `data-middleware-ai-infrastructure` | SQL, Redis, messaging, Elasticsearch, object storage, GPU, Docker, Kubernetes, and networking |
| `log-observability-analysis` | Logs, metrics, traces, profiling, alerts, and change events |
| `engineering-quality-delivery` | Modification, tests, Git, release, rollback, approval, and final delivery |
| `multi-agent-independent-review` | Pre-implementation review for high-risk changes and independent review after behavior changes |
| `technical-document-writing` | Technical solutions, architecture, APIs, deployment, incidents, and formal reports |
| `long-running-task-memory` | Cross-session, multi-stage, multi-module, multi-agent, and context-compaction work |
| `controlled-evolution-governance` | Cross-task review, self-observation, cost routing, reviewer value, and Proposal governance |

Automatic routing is normally sufficient. To constrain a task explicitly:

```text
Use $python-backend-ai-engineering to inspect concurrency in this FastAPI service.
Analyze first; do not modify anything.
```

```text
Use $frontend-engineering to fix state desynchronization on this React page,
then use $engineering-quality-delivery for tests and delivery validation.
```

Each phase should default to one primary domain Skill plus only the necessary quality, log, review, documentation, or long-running-task support. Do not select every Skill merely for formality.

## 6. The 7 Reviewers

| Reviewer | Responsibility |
|---|---|
| `cp_review_functional_business` | Functional correctness and business definitions |
| `cp_review_compatibility_regression` | Existing behavior, regression, and compatibility |
| `cp_review_security_access` | Authentication, authorization, privilege escalation, injection, and sensitive data |
| `cp_review_performance_resources` | SQL, I/O, connections, threads, queues, and resource load |
| `cp_review_data_contract` | Databases, APIs, Redis, messaging, serialization, and consistency boundaries |
| `cp_review_state_concurrency` | Races, idempotency, timeouts, retries, cancellation, and state boundaries |
| `cp_review_test_delivery` | Test evidence, failures, documentation, and delivery boundaries |

Let the agent choose:

```text
After the repair, select only the independent reviewers justified by actual risk and conduct a
read-only review. Do not start all reviewers merely for formality.
```

Select one explicitly:

```text
Start cp_review_security_access with Luna Low.
Read-only inspect authorization, privilege escalation, and sensitive-data risk.
```

Reviewer TOML files do not pin models. The automatic cost route is:

```text
Luna Low -> Luna Medium -> Terra Medium -> Terra High
```

Automated work is capped at Terra High. The PreToolUse Hook rejects explicit Sol, `xhigh/max/ultra`, unknown models, and any model that cannot be proven to stay within the ceiling.

## 7. Long-Running Tasks and Checkpoints

Ordinary one-shot tasks record only minimal lifecycle events. Cross-session, multi-stage, multi-module, or multi-agent tasks should use long-running-task memory:

```text
This is a long-running task.
Use $long-running-task-memory to manage the objective, plan, authorization, evidence, risks,
and checkpoints. Write a checkpoint after every independently recoverable phase and continue until
all acceptance criteria are complete.
```

Maintain at least:

```text
CURRENT_TASK.md
PROGRESS.md
PLAN.md
```

When resuming:

```text
Resume the previous long-running task. Read the current task, current plan phase, and three most recent
checkpoints, then verify current Git, source, and runtime state before continuing.
```

Checkpoints preserve only verifiable facts, evidence, authorization, state, risks, and next actions—not lengthy internal reasoning. A Task Checkpoint is not automatically promoted to project memory or cross-project knowledge.

## 8. What Automatic Self-Observation Records

The six Hooks record:

```text
UserPromptSubmit -> TURN_OPENED
PreToolUse       -> PRE_TOOL_GUARD
SubagentStart    -> SUBAGENT_STARTED
SubagentStop     -> SUBAGENT_STOPPED
Stop             -> TASK_COMPLETED
SessionEnd       -> SESSION_ENDED
```

TaskOutcomeEvent V2 stores minimal structured metadata such as:

- event, session, turn, and task IDs;
- `project_id + repo_fingerprint`;
- actual model and reasoning effort;
- reviewer, finding, and repair-round counts;
- an explicit terminal result, or `UNKNOWN` when absent; and
- a forward SHA-256 hash chain with optional HMAC.

V6.3 also computes lifecycle completeness, SessionEnd coverage, duplicate or out-of-order events, cross-task or cross-session contamination, and project/repository binding coverage. Reviewer value is evaluated only when a finding can be linked to adoption, repair, or regression-prevention evidence; without causal evidence it is `insufficient-evidence`.

Raw prompts, full responses, source text, diffs, tokens, cookies, API keys, and other credentials are not stored by default. Data that did not exist before V6.3 installation is never fabricated retroactively.

## 9. Controlled Evolution and Review

Controlled evolution is for cross-task review, reviewer value, model cost, Skill-routing deviation, and the assistant's own version governance—not ordinary coding.

Recommended prompt:

```text
Use $controlled-evolution-governance to analyze recent Event, Checkpoint, Review, and Evidence records
for this project. Generate a Snapshot, Assessment, and Optimization Proposal.
Generate proposals only; do not accept or implement them automatically.
```

Standard chain:

```text
Lifecycle Event
  -> task aggregation
  -> Self Observation Snapshot
  -> Value / Complexity Assessment
  -> Optimization Proposal
  -> human ACCEPT / REJECT / DEFER
  -> separate implementation task after ACCEPT
  -> independent validation and Proposal closure
```

When evidence is insufficient, the agent must use `UNKNOWN`, list the gaps, or stop Proposal generation. It must not infer success from a generic `status` or borrow another project's data.

Regardless of Proposal status, `execution_authorization` is always `NONE`. Human `ACCEPT` endorses the optimization direction only; it does not authorize file modification, commit, push, deployment, or production operations.

## 10. Authorization and Security Boundaries

Package workflows never automatically obtain authority to:

- modify business code, Skills, reviewers, routing, or global configuration;
- accept or execute an Evolution Proposal;
- create a Git commit or push;
- deploy, restart, or make a change effective;
- modify a database or production data; or
- operate in production.

Even when an action is explicitly authorized, it must remain bound to the current project, task, environment, and baseline, and actual state must be read back afterward. Test evidence cannot substitute for operational authorization.

## 11. Recommended Task Template

```text
Please handle this task:

Objective:
[Describe the problem or deliverable]

Execution constraints:
1. First confirm the project, technology stack, call chain, data boundary, and current baseline.
2. State the root cause or implementation plan before making the minimum sufficient change.
3. Do not modify unrelated files or casually upgrade unrelated dependencies.
4. Complete targeted tests and necessary regression validation.
5. Select only the independent reviewers justified by risk.
6. In the final report, state separately: modified, validated, reviewed, committed,
   pushed, deployed, restarted, and effective.
7. Do not commit, push, deploy, restart, or operate in production without authorization.
```

## 12. Maintenance, Validation, and Troubleshooting

Inspect the Plugin:

```powershell
codex plugin list --json
```

Re-verify installation:

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
```

Validate the release package itself:

```powershell
python scripts\validate-package.py
python scripts\routing-eval.py validate
```

Validate official ZIP determinism and its machine attestation:

```powershell
python scripts\build-release.py verify --archive ..\Codex-Skills-V6.3.zip
python scripts\release-attestation.py verify --attestation ..\release-attestation-v6.3.json --artifact ..\Codex-Skills-V6.3.zip
```

### Plugin Files Exist but the Plugin Is Disabled

Treat `codex plugin list --json` as authoritative. Re-run the installer or the Marketplace/Plugin registration steps it reports; copied files alone do not prove success.

### Windows Hook Cannot Find Python

V6.3 does not require `python3.exe`. Confirm that account-level Python, `python.exe` on PATH, or the `py.exe` launcher is available.

### Non-English Stop or Hook Output Is Corrupt

Confirm that the active Plugin version is 6.3.0 and all six Hooks start through `cp_hook.cmd`. Close and reopen Codex tasks that were open before upgrading.

### Project Events Do Not Enter Aggregation

Confirm that both recorded `project_id` and `repo_fingerprint` match. Any mismatch is rejected by the safety policy.

### Historical Tasks Lack Review Data

V6.3 does not backfill pre-installation events. Use existing Git, logs, tests, old checkpoints, and Evidence, and keep unsupported areas unverified. Explicitly enable long-running-task memory for future work.

### Interrupted Installation

Do not delete the entire `.codex`, `.agents`, or plugins directory. Run:

```powershell
python scripts\package_manager.py status --scope user
python scripts\package_manager.py recover --scope user
```

Recovery reverses recorded managed actions from the transaction log and restores the previous Plugin registration. Unknown content or ownership conflicts cause a stop while preserving logs.

## 13. Uninstall and Recovery

Inspect the uninstall plan:

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin --dry-run
```

Uninstall:

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin
```

Uninstall restores managed files from the upgrade backup and refuses to overwrite external changes by default. Use `--force` only after confirming that managed drift should be overwritten.

Project context, self-observation Event, Snapshot, Assessment, Proposal, and historical backups are not deleted by an ordinary uninstall.

See `docs/INSTALLATION_RECOVERY.md` for the complete recovery rules.

## 14. Acceptance Checklist

- [ ] `codex --version` is the target version 0.150.1
- [ ] `doctor` reports V6.3.0 and the correct native Windows `CODEX_HOME`
- [ ] Dry-run reports no path, Reparse Point, drift, or rollback blocker
- [ ] Formal installation exits with code 0
- [ ] `verify --mode plugin` passes
- [ ] Plugin reports `installed=true`, `enabled=true`, and `version=6.3.0`
- [ ] All 10 Skills are discoverable
- [ ] All 7 reviewers are discoverable and do not pin models
- [ ] All 6 Hooks load and SessionEnd timeout is 3 seconds
- [ ] No `python3.exe` shim is required
- [ ] Primary-agent model configuration is unchanged
- [ ] Historical project context and upgrade backups remain intact
- [ ] Active installation transaction is cleared and committed transaction archives remain traceable
- [ ] Two clean ZIP builds are byte-identical
- [ ] Machine attestation binds the official ZIP, Codex version, Plugin, and validation-evidence hashes
- [ ] A real session produces all five lifecycle event types with a continuous hash chain
