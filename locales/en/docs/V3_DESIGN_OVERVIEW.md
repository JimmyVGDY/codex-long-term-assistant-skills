# v3.0 Foundation Design: Continuous External Memory and Independent Multi-Agent Review

> Historical design document: V4.2 replaced the budget and workflow defaults described here. Current behavior is defined by `V4_2_COST_FLOW_OPTIMIZATION.md`, `MODEL_ROUTING_AND_COST_POLICY.md`, and the actual scripts.

## 1. Upgrade Objectives

v3.0 addresses two systemic problems in long-running agent work:

1. **Incomplete review causes repeated repair cycles.** A single reviewer can miss issues that cross functional, compatibility, security, performance, data, and concurrency dimensions. The implementing agent then repeats “find one, fix one, find another.”
2. **Context compaction loses task state.** When objectives, authorization, completed steps, validation results, and next actions exist only in conversation context, compaction, model changes, interrupted sessions, or multi-agent collaboration can break continuity.

This release follows two tracks:

- **Independent multi-agent review:** parallel discovery, unified attribution, consolidated repair, and targeted re-review.
- **Continuous external checkpoints:** context is a short-term cache; deterministic local documents carry long-term task state.

---

## 2. Overall Architecture

```text
Global AGENTS.md
    ├── hard rules for authority, truthfulness, minimum change, and production safety
    ├── default multi-agent review limits
    └── default continuous-checkpoint constraints

On-demand Skills
    ├── technology-domain Skills
    │   ├── Java
    │   ├── Python / AI
    │   ├── Vue
    │   └── data / middleware / infrastructure
    ├── engineering-quality-delivery
    ├── multi-agent-independent-review
    ├── long-running-task-memory
    └── technical-document-writing

Narrow-responsibility custom reviewers (graded by runtime isolation)
    ├── functional and business
    ├── regression and compatibility
    ├── access and security
    ├── performance and resources
    ├── data and contracts
    ├── state and concurrency
    └── tests and delivery
```

`SKILL.md` retains only triggers, mandatory entry points, critical parameters, and composition boundaries. Detailed rules live in `references/`, templates in `assets/`, and helpers in `scripts/`, avoiding full injection of every rule into every task.

---

## 3. Independent Multi-Agent Review Design

### 3.1 Minimum Effective Repair Rounds

The formal principle is:

> **Discover once, attribute uniformly, repair in a consolidated pass, and re-review only the affected scope—aiming for the fewest effective repair rounds.**

“Fewest” does not mean forcing completion in one round, and it never justifies ignoring new findings. It means:

- cover distinct specialist dimensions as broadly as practical in the first round;
- do not make piecemeal changes before every reviewer in the round returns;
- have the primary coordinating agent deduplicate findings and merge those with one root cause;
- define the smallest repair set that fully resolves the blocking root causes;
- after consolidated repair, re-review only affected areas; and
- continue when a genuine blocker remains, but never loop without limit.

### 3.2 More Reviewers Are Not Always Better

Default selection by risk:

| Risk | Recommended reviewer count |
|---|---:|
| Low | 1-2 |
| Medium | 3-4 |
| High | 5-6 |
| Critical | Up to 6 in round one, then targeted additions based on evidence gaps |

Prioritize different responsibilities. Do not start multiple reviewers with identical task scope merely to reach a count.

### 3.3 Central Coordination, Leaf Reviewers, and Isolation Grades

The package uses a centrally coordinated model:

- The primary coordinating agent selects reviewers, maintains the budget, waits for every result, consolidates findings, and decides whether another round is needed.
- Every custom reviewer TOML declares `read-only`, but a declaration does not prove system-level runtime isolation.
- Behavioral rules prohibit reviewers from modifying files, committing, pushing, deploying, restarting, or writing data.
- A writable parent session is `logical-readonly` by default. Strict review requires a fully read-only parent session or valid system-isolation evidence.
- Reviewers do not spawn other agents; they may recommend a specialist follow-up.
- Depth-2 or depth-3 specialist reviewers are still launched by the primary coordinating agent within the budget.

This is more controllable than unrestricted reviewer recursion and prevents explosive trees and duplicate review.

### 3.4 Hard Limits

```text
MAX_REVIEW_AGENT_DEPTH = 3
MAX_REVIEW_ROUNDS = 3
MAX_PARALLEL_REVIEWERS = 6
MAX_TOTAL_REVIEW_AGENTS_PER_BOUNDARY = 12
MAX_REPAIR_ROUNDS = 3
```

Meaning:

- depth 0: primary coordinator;
- depth 1: first-round specialist reviewer;
- depth 2: conflict resolution, evidence completion, or specialist second opinion;
- depth 3: final targeted re-review;
- no automatic spawning after depth 3;
- no more than three review rounds and three consolidated-repair rounds per feature boundary;
- no more than six concurrent reviewers; and
- no more than twelve cumulative reviewers across all rounds.

When any limit is reached, stop the automatic loop and report remaining blockers, unverified items, and decisions required. Never claim success merely to close the workflow.

### 3.5 Consolidating Results

The primary coordinating agent must maintain one ledger containing at least:

- finding ID;
- reviewer and review dimension;
- evidence grade;
- location and trigger;
- impact scope;
- whether the current change introduced it;
- root cause;
- severity and blocking status;
- related findings with the same root cause;
- repair boundary; and
- post-repair validation method.

When several symptoms share one root cause, merge them into one complete repair boundary. For example, duplicate message consumption, incorrect ACK timing, a missing unique constraint, and a missing idempotency record should be handled together as “incomplete consumer idempotency and success boundary,” not as four separate edits.

---

## 4. Continuous External Memory Design

### 4.1 Context Is Not a Long-Term State Store

The formal principle is:

> Conversation context carries short-term reasoning for the current small step. Persist confirmed objectives, authorization, progress, evidence, decisions, blockers, and next actions continuously in external task documents.

The target recovery boundary is:

> If context is suddenly compacted or interrupted, at most the one currently incomplete step may be lost. Every previously completed step must be recoverable from documents.

Therefore:

```text
MAX_UNPERSISTED_COMPLETED_NODES = 0
```

### 4.2 Independently Recoverable Small Steps

Typical steps that require immediate persistence include:

- completing review of a module, call chain, or data flow and reaching a conclusion;
- confirming a root cause or excluding an important candidate;
- completing a group of changes within one feature boundary;
- completing a build, test, migration, export, or minimum reproduction;
- dispatching, collecting, or consolidating a reviewer round;
- defining the smallest complete repair set;
- completing consolidated repair or targeted re-review;
- encountering a blocker, failure, scope change, or authorization change;
- committing, pushing, deploying, restarting, or completing environment validation; and
- preparing to pause, wait for confirmation, or end the session.

A single `ls`, `grep`, inconclusive read, or immediately reverted attempt does not need its own checkpoint.

### 4.3 Two Hot Documents

Every checkpoint updates at least:

1. `PROGRESS.md`: append historical facts and evidence.
2. `CURRENT_TASK.md`: overwrite with the latest recoverable snapshot.

Update other documents when their event occurs:

| Event | Document |
|---|---|
| Plan or phase change | `PLAN.md` |
| Stable long-term project facts | `PROJECT_CONTEXT.md` |
| Important technical or business decision | `DECISIONS.md` |
| Out-of-scope issue | `KNOWN_ISSUES.md` |
| Pause, compaction, or agent handoff | `HANDOFF.md` |
| Actual delivery | `DELIVERY_RECORD.md` |
| Raw reviewer result | `reviews/<task>/<round>/` |

### 4.4 Checkpoint Transaction

Run each checkpoint in this order:

```text
Re-read the latest shared documents
    ↓
Generate a unique checkpoint ID
    ↓
Append the record to PROGRESS.md
    ↓
Refresh the latest snapshot in CURRENT_TASK.md
    ↓
Verify matching final checkpoint ID and state version
    ↓
Continue to the next step
```

If `PROGRESS.md` was appended but refreshing `CURRENT_TASK.md` failed, use `checkpoint.py repair` to reconstruct the current snapshot from the final checkpoint.

### 4.5 Prevent Long Unpersisted Runs

Even before a complete step is finished, write an in-progress checkpoint after no more than five consecutive substantive actions:

```text
MAX_SUBSTANTIVE_ACTIONS_WITHOUT_CHECKPOINT = 5
```

### 4.6 Double Checkpoints for High-Risk Operations

For high-risk, irreversible, or partially successful operations:

- Before the operation, record the objective, authorization, impact, backup, rollback, stop conditions, and “not started” state.
- Afterward, record the actual command, success/failure/partial status, actual impact, rollback state, and next validation.

If context is interrupted mid-operation, a recovering agent can still determine the real state.

### 4.7 Single Memory Writer

```text
SINGLE_MEMORY_WRITER = true
```

- Only the primary coordinating agent writes shared task documents.
- A subagent returns structured results or writes only the separate reviewer report explicitly assigned to it.
- Re-read the latest content before every shared write.
- `checkpoint.py` uses a lock file and atomic replacement to reduce concurrent overwrite and partial-write risk.

### 4.8 Hot and Cold Tiers

Defaults:

```text
RECENT_CHECKPOINTS_TO_LOAD = 5
HOT_PROGRESS_CHECKPOINT_LIMIT = 30
```

- During recovery, read the current snapshot and five most recent checkpoints in full.
- Keep no more than 30 checkpoints in active `PROGRESS.md`.
- Archive older records under `archive/`; hot documents retain only an index.
- Recovery does not need to load the complete history every time.

---

## 5. Recovery Protocol

After context compaction, session recovery, or an agent change:

1. Read the current request and authorization.
2. Read global and project-level `AGENTS.md`.
3. Read `PROJECT_CONTEXT.md`, `CURRENT_TASK.md`, and the current phase in `PLAN.md`.
4. Read the three to five most recent checkpoints in `PROGRESS.md`.
5. Follow references to relevant decisions and reviewer reports.
6. Inspect Git branch, HEAD, worktree, untracked files, and diff.
7. Verify source, configuration, and validation evidence.
8. Compare documented state with actual state.
9. Re-read core code involved in the next action.
10. Continue only after the states agree.

If branch, HEAD, diff, authorization, or environment conflicts, stop and write a state-divergence checkpoint before reusing any earlier conclusion.

---

## 6. Combined Execution Flow

```text
Recover external memory and verify the repository
    ↓
Complete one recoverable small step
    ↓
Append PROGRESS and refresh CURRENT_TASK
    ↓
Complete the feature-boundary change
    ↓
Run minimum targeted validation
    ↓
Write a review-start checkpoint
    ↓
Run reviewers in parallel and record system-readonly / logical-readonly
    ↓
Wait for all results and attribute them consistently
    ↓
Write a consolidation checkpoint
    ↓
Apply the smallest complete repair set in one pass
    ↓
Re-run affected validation
    ↓
Re-review affected dimensions only
    ↓
Update CHANGELOG, delivery records, and Commit
```

Quality gates and task continuity reinforce each other: review aims to discover the complete problem set in as few passes as possible, while external memory ensures accurate continuation after context compaction at any step.

---

## 7. Explicit Boundaries

- Multi-agent review does not replace builds, tests, database validation, or production acceptance.
- External documents do not override current source, configuration, Git, or runtime facts.
- “Completed” in a document does not prove actual completion.
- Reviewers cannot expand authorization through review, and TOML declarations are not runtime isolation evidence.
- Reducing repair rounds does not justify unrelated refactoring.
- Do not duplicate review merely to reach a reviewer count.
- Stop automatic loops at their limits and report honestly.
- External task documents must not enter the project repository, Git history, or project `CHANGELOG`.

---

> v3.1 added the log and observability analysis design; see `V3_1_LOG_ANALYSIS_DESIGN.md`.

> v3.3 corrected reviewer runtime isolation; see `REVIEWER_RUNTIME_ISOLATION.md`.
