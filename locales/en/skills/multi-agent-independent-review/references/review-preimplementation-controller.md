# Preimplementation Review and State Controller

## 1. When to Review Before Implementation

Prioritize preimplementation review for public API, message, cache, or serialization contracts; database migrations; authorization boundaries; core state machines; cross-service data ownership; high-concurrency resource budgets; production migrations; and difficult rollback.

A local low-risk repair without a shared contract normally does not require multi-agent review before implementation.

## 2. Minimum Input

First create a reviewable design containing goals and non-goals, success boundaries, confirmed facts and assumptions, affected modules and contracts, recommendation and alternatives, compatibility, security, performance, migration, rollback, and minimum postimplementation validation.

Do not ask reviewers to discuss an entire system without design boundaries.

## 3. Reviewer Composition

Use one or two complementary reviewers by default. Critical work may need three, but the default controller budget remains two until explicitly relaxed.

- Functional/business and data/contract review normally use `terra-medium`.
- Compatibility and initial performance review may use `luna-medium`.
- One reviewer may use `terra-high` only when security, concurrency, irreversible migration, or core-state risk is explicitly present.

Before implementation, review the design, contracts, call chains, and known facts only. Do not present hypothetical defects in code that does not yet exist as confirmed findings.

## 4. Consolidation Gate

After collecting results, deduplicate and consolidate by root cause. Distinguish design defects, risk assumptions, evidence gaps, and out-of-scope recommendations. Implementation begins only after blocking design issues are resolved.

Allowed conclusions: passed; passed after revision; blocking issues; incomplete.

## 5. State Controller

`scripts/review_controller.py` maintains the ledger only; it does not start agents. Recommended sequence:

```text
init -> isolation -> plan -> dispatch -> result -> merge -> repair(as needed) -> validate/status -> close
```

The controller records functional boundary, risk, isolation, budget, packet hash, model tier, dispatch, results, and stopping state. After context compaction or agent switching, run `status` or `validate` before continuing; do not rely on conversation memory alone.

Preimplementation reviewers count toward the default total budget of six for one functional boundary, so preserve capacity for targeted postimplementation review.
