# Stopping Conditions, Structured Output, Ledger, and Long-Term Memory

## 1. Stopping Conditions

Normal stop: blocking issues are resolved; high-severity issues are resolved or explicitly accepted; minimum targeted validation remains valid; affected contracts were rereviewed; the diff is stable; and unverified items are recorded.

Constrained stop that cannot be called a pass: a depth, round, repair, reviewer-count, Terra High, or platform-concurrency limit is reached; environment or permissions are missing; conflict cannot be adjudicated; further work would expand scope; or the requester must decide a business definition or risk acceptance.

Stop adding reviewers when:

- the previous round passed the same packet without findings;
- the same reviewer already reviewed the same packet without an explicit second-opinion reason;
- another round would inspect no new scope, validate no new hypothesis, and adjudicate no blocking conflict;
- expected new information cannot change the gate conclusion.

Postimplementation review has at most two rounds by default. A third round is only a compatibility hard ceiling, requires explicit relaxation, and may contain only one reviewer adjudicating a remaining blocker.

## 2. Structured Reviewer Output

Reviewers use `review-result.schema.json`, containing at least:

- reviewer, round, functional boundary, and packet hash;
- requested and actual model, reasoning effort, and assignment state;
- isolation level;
- checked scope and unverified items;
- conclusion;
- severity, evidence, location, trigger, impact, root cause, repair boundary, and validation for each finding.

Merge findings with one root cause and use at most eight root-cause groups by default. Do not return the complete diff, long raw logs, or internal reasoning. Even a no-findings result must list checked scope and evidence gaps.

## 3. Coordinating Ledger

Record reviewer responsibility, model tier, state, packet hash, deduplication relationships, root-cause groups, blockers, repair, validation, rereview, isolation evidence, and remaining budget. Store raw structured results under `reviews/<task>/round-N/`; store only indexes and consolidated conclusions in main progress.

When actual tier exceeds the request or approved set, mark `mismatch`. Before closing, explicitly acknowledge the policy violation; never pass silently.

## 4. Long-Running Task Memory

With `$long-running-task-memory`, use event-driven checkpoints rather than rewriting documents for each dispatch and return. Persist at least four recoverable nodes:

1. Review packet, plan, budget, and first-round dispatch are fixed.
2. The round is collected and consolidated by root cause.
3. Centralized repair and affected validation are complete.
4. Final targeted rereview and gate conclusion are complete.

Only the coordinating agent writes shared memory. Reviewers return structured results or write an explicitly assigned independent report.
