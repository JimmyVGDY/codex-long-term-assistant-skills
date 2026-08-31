# Codex Skills Usage Examples (v3.3)

## 1. Analyze Local Log Files

```text
Use $log-observability-analysis.

Analyze the application logs, rotated logs, and compressed log archives in the current directory.
First list each file, its size, time range, time zone, encoding, and completeness. Process files
in bounded chunks without overwriting the originals. Build anomaly clusters, a cross-file timeline,
and an evidence ledger that distinguishes confirmed, highly probable, speculative, and unverified
claims. Redact sensitive data in the output, and do not treat temporal correlation as proof of cause.
```

## 2. Read-Only Cross-Component Production Log Analysis

```text
Use $log-observability-analysis, $java-backend-engineering,
and $data-middleware-ai-infrastructure.

In production, perform only the read-only log, monitoring, and low-risk state queries covered by
the current authorization. Analyze application, HikariCP, MySQL, RabbitMQ, and container logs from
the last 60 minutes. Normalize time zones and correlate evidence by traceId and timeline. Do not
modify or clean anything, restart services, deploy, shift traffic, or write data. Do not use an
unbounded tail -f, unbounded scans, KEYS *, or expensive full-table queries.
```

## 3. Cross-Session Log Troubleshooting

```text
Use $log-observability-analysis and $long-running-task-memory.

Analyze application, database, middleware, and infrastructure sources in parallel using read-only
access. The primary agent must consolidate the timeline, evidence grades, and candidate root causes.
After every recoverable step, append to PROGRESS.md and refresh CURRENT_TASK.md. Subagents must not
modify shared memory.
```

## 4. Local Java Repair with Continuous Checkpoints and Strict Review

```text
Use $java-backend-engineering, $data-middleware-ai-infrastructure,
$engineering-quality-delivery, $multi-agent-independent-review,
and $long-running-task-memory.

Read the complete relevant call chain, then repair the current API issue while preserving existing
business behavior. Immediately update CURRENT_TASK.md and PROGRESS.md after every independently
recoverable step. Completed work must not exist only in the conversation.

After the targeted backend tests pass, select reviewers by current risk and record whether this round
is system-readonly or logical-readonly. Do not make piecemeal changes while first-round findings are
still arriving. The primary coordinating agent must deduplicate findings, cluster root causes, resolve
conflicts, grade severity, and then apply the smallest complete repair set in one consolidated pass.
Allow at most three review rounds and three consolidated-repair rounds; stop honestly and report when
the limit is reached. Update the project's existing CHANGELOG, create a local commit, and do not push.
```

## 5. Comprehensive Read-Only Multi-Agent Review

```text
Use $multi-agent-independent-review, $java-backend-engineering,
and $data-middleware-ai-infrastructure.

Review the actual git diff between the current branch and its baseline without modifying it. Based on
risk, choose the necessary reviewers from functional/business correctness, compatibility/regression,
security/access, performance/resources, data/contracts, state/concurrency, and test/delivery evidence.
Run no more than three reviewers in parallel by default. Prefer Luna for test and compatibility scans;
use Terra only when business semantics or high-risk judgment requires it. Automated work must never
exceed Terra High. Consolidate all findings only after the whole round returns.

Do not modify files, create commits, push, deploy, restart, or write data. Report blocking findings,
non-blocking findings, unverified items, and the recommended smallest complete repair set.
```

## 6. Large Cross-Session Refactor

```text
Use $long-running-task-memory, $engineering-quality-delivery,
and the Skills for the current technology stack.

Read or initialize the external-memory documents outside the repository. Treat conversation context
as temporary storage for the current small step: append to PROGRESS.md and refresh CURRENT_TASK.md
after every recoverable step. Create a checkpoint after no more than eight consecutive substantive
actions, and record separate checkpoints before and after high-risk operations.

After context compaction, a model change, or session recovery, first read the current authorization,
task snapshot, plan, three most recent checkpoints, and relevant decisions. Then verify the branch,
HEAD, git status, git diff, source, configuration, and validation evidence. If they conflict, record
the state divergence before making any further change.
```

## 7. Create a Checkpoint Before Dispatching Reviewers

```text
Use $multi-agent-independent-review and $long-running-task-memory.

The current code and minimum targeted validation are stable. First write a review-start checkpoint
that records the feature boundary, baseline, diff scope, reviewer list, round, depth, and remaining
budget. Then dispatch functional, compatibility, security, performance, data, and concurrency
reviewers in parallel. Subagents must not modify shared memory. After every result returns, the primary
coordinating agent writes the consolidated-review checkpoint and evidence ledger.
```

## 8. Write a System Architecture Design

```text
Use $technical-document-writing, $java-backend-engineering,
$python-backend-ai-engineering, and $data-middleware-ai-infrastructure.

Write a system architecture design from the repository's actual code, configuration, and deployment
files. Do not invent components that are not implemented. Distinguish confirmed facts, inferences,
and unverified items. Cover system boundaries, service responsibilities, data ownership, APIs,
caching, messaging, access control, deployment, monitoring, capacity, risk, and evolution paths.
```

## 9. Comprehensively Restructure Existing Documentation

```text
Use $technical-document-writing.

Read all existing Markdown documents, then comprehensively restructure them without changing any
confirmed business definition. Remove duplication, repair heading levels, normalize terminology, and
add scope, non-goals, risks, validation, and rollback. Mark unsupported statements as needing
confirmation instead of inventing facts.
```

## 10. Troubleshoot and Review a Python AI Worker Failure

```text
Use $python-backend-ai-engineering, $data-middleware-ai-infrastructure,
$technical-document-writing, and $long-running-task-memory.

Investigate an intermittently stalled GPU worker using read-only access. Write a checkpoint after
every clear exclusion or confirmation. Correlate logs, processes, threads/coroutines, queues, database
connections, NAS I/O, GPU memory, and task state. Provide multiple candidate causes, validation steps,
temporary containment, and a permanent solution. Grade insufficiently supported conclusions as highly
probable, speculative, or unverified. Finish with a formal incident analysis report.
```

## 11. Pause for Confirmation Before Production Operations

```text
Use $engineering-quality-delivery and $long-running-task-memory.

Begin with read-only inspection of production and the current version. Write a pre-operation
checkpoint recording the target environment, instances, impact scope, authorization, backup,
rollback, acceptance criteria, and stop conditions. Until the current task explicitly authorizes
writes, do not modify databases, Redis, messaging, or files, and do not deploy, restart, or shift traffic.
```

## V4.2 Foundation: Model Tiers and Cost Convergence

```text
Use the primary agent for decisions. Delegate only independent, read-intensive subtasks that can
return structured results. Select models progressively: luna-low -> luna-medium -> terra-medium ->
terra-high. Prefer Luna for search, extraction, test evidence, and compatibility scans. Use Terra for
business semantics, transactions, concurrency, and security only when needed. Automated subagents must
never exceed Terra High and must never automatically use Sol, xhigh, max, or ultra. Default to no more
than three concurrent and six cumulative subagents. Do not ask the same reviewer to inspect an unchanged
packet again.
```

## V4.1 Foundation: Pre-Implementation Design and Impact Review

```text
Use $data-middleware-ai-infrastructure and $multi-agent-independent-review.

This change adds a database field and a message field and backfills historical data. Before writing
code or a migration, define the objective, non-goals, compatibility, staged rollout, and rollback plan.
Then run one read-only pre-implementation review across functional, compatibility, data, and performance
dimensions. Revise the design only after all reviewer results return. Pre-implementation review does
not replace targeted tests and independent post-implementation review.
```

## V4.1 Foundation: Multi-Signal Observability Analysis

```text
Use $log-observability-analysis and the Skill for the current technology stack.

Read-only correlate application logs, P95/P99, error rate, connection pools, message backlog,
distributed traces, existing JFR/thread dumps, alerts, and release events from the same time window.
Normalize time zones and sampling ranges before building a multi-source evidence timeline. Do not infer
that a release caused an anomaly merely because it came first, and do not collect a new production
profile.
```

## V4.1 Foundation: Minimum Sufficient Loading

```text
Choose one primary domain Skill for the current phase and add no more than two necessary supporting
Skills. Do not preload Git, review, documentation, or long-term-memory workflows for later phases.
If more than four Skills are required at once, first state the unique responsibility of each one.
```

## V4.1 Foundation: Review State Controller

```text
Use $multi-agent-independent-review and $long-running-task-memory.
Initialize review-state.json for the current feature boundary. Update controller state whenever review
is planned, dispatched, collected, consolidated, or followed by a consolidated repair. After context
compaction, run status / validate first and do not dispatch more work until the remaining budget is
confirmed.
```

## v3.3: Strict Read-Only Review

```text
Use $multi-agent-independent-review.

This task touches production permissions and real data, so use Level A system-readonly. First confirm
that the parent session is actually read-only. If it is writable, stop before dispatching reviewers;
do not claim system isolation from reviewer TOML sandbox_mode alone. Record the actual agent type,
configuration path, parent-session sandbox, isolation level, and unverified items.
```

## v3.3: Logical Read-Only Review in a Writable Session

```text
Use $multi-agent-independent-review.

The current parent session uses danger-full-access, so this round may be labeled only logical-readonly.
Reviewers must still obey the behavioral rules: no file modification, commits, or further delegation.
The final report must state that independent reasoning was completed but system-level write isolation
was not guaranteed.
```

## V4.1 STANDARD Repair Example

```text
Use $java-backend-engineering and $engineering-quality-delivery.
Use the STANDARD tier and create a task execution envelope first. Complete the relevant targeted tests
and bind their evidence fingerprints. Start reviewers only when risk requires them, using independent
context and one consistent review packet.
```

## V4.1 STRICT Migration Example

```text
Use $data-middleware-ai-infrastructure, $engineering-quality-delivery,
$multi-agent-independent-review, and $long-running-task-memory.
Use the STRICT tier. Complete pre-implementation review and rollback design first. After implementation,
review in parallel from independent contexts. Every reviewer must use the same packet hash, and delivery
may begin only after all blocking findings are resolved.
```
