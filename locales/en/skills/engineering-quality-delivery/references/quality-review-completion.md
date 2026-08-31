# Postimplementation Review and Completion Definition

## Contents

- 7. Independent Postimplementation Review and Multi-Agent Gate
- 8. Definition of Done

## 7. Independent Postimplementation Review and Multi-Agent Gate

### 7.1 Purpose

This section governs postimplementation review. Preimplementation design review does not replace a stable `git diff`, minimum targeted validation, or postimplementation review.

Review reduces the chance that a repair introduces new bugs, regresses existing behavior, changes business definitions, creates authorization or security vulnerabilities, adds performance/resource cost, or creates new state and boundary problems. It does not replace runtime tests.

### 7.2 Triggers

Normally trigger when code or executable content changes runtime behavior, including backend, frontend, shared libraries, scripts, workers, schedulers, data processing, exports, migrations, and logical configuration.

Normally do not trigger for:

- commit splitting or message correction;
- CHANGELOG layout only;
- read-only investigation or static analysis without code change;
- ordinary wording changes without behavior change.

Production, authorization, money, data migration, core state, and high-concurrency paths must not be exempted without reason.

### 7.3 Preferred Strict Multi-Agent Gate

When available, combine `$multi-agent-independent-review` and use distinct reviewers according to risk. Distinguish `system-readonly` from `logical-readonly`. Cover function/business, regression/compatibility, authorization/security, performance/resources, data/contracts, state/concurrency, and test/delivery.

Requirements:

- reviewers are read-only and do not modify, commit, push, deploy, restart, or perform production writes;
- do not repair findings as they arrive before all round-one reviewers return;
- the coordinator deduplicates, clusters root causes, adjudicates conflicts, and assigns severity;
- form the minimum complete repair set before centralized repair;
- rereview only affected scope after repair, expanding when a public boundary changed;
- respect the active reviewer's conservative defaults and hard ceilings; do not use maxima as routine budgets;
- after reaching a limit, stop automatic looping and retain blockers and unverified items rather than claiming a pass.

The `$multi-agent-independent-review` skill defines detailed roles, packets, output, and stopping. With `$long-running-task-memory`, checkpoint the review plan, dispatch, collection, consolidation, repair, revalidation, and final rereview at recoverable nodes. Only the coordinator updates shared memory.

### 7.4 Compatibility Gate in a Restricted Environment

Use only when tools objectively cannot provide an independent reviewer and strict gating is not mandatory:

1. Switch to a read-only review phase after implementation.
2. Re-read actual `git diff`, full context, call chains, contracts, and test evidence.
3. Do not use implementation expectations as conclusions.
4. Report findings, evidence, severity, blockers, and unverified items across six dimensions.
5. Label it “isolated secondary review, not a truly independent reviewer.”
6. Let the current task card or explicit authorization decide whether commit is allowed.

Never present a compatibility gate as strict independent review.

### 7.5 Standard Order

```text
Complete the functional-boundary change
    -> Run minimum targeted validation
    -> Stabilize the current git diff
    -> Run parallel independent review or restricted compatibility review
    -> Consolidate and define the minimum complete repair set
    -> Implementation agent repairs blockers centrally
    -> Rerun affected validation
    -> Rereview affected scope
    -> Update formal documentation or CHANGELOG
    -> Inspect diff and commit
```

Any code change after review invalidates and requires rerunning affected validation and review.

### 7.6 Six Core Dimensions

1. Authorization and privilege escalation.
2. Security.
3. Functional correctness and business definitions.
4. Regression and compatibility.
5. Performance and resource burden.
6. State, interaction, and new boundaries.

Test evidence and delivery boundaries are additional specialist dimensions.

### 7.7 Output and Conclusions

Report functional boundary, diff baseline, files, call chains, reviewers and rounds, six-dimensional conclusions, consolidated issues, severity, root-cause groups, blockers, unverified items, repair rounds, and final conclusion.

Severity: blocking, high, medium, low, recommendation.

Allowed final conclusions:

- passed with no blockers;
- non-blocking issues remain;
- blocking issues remain;
- review limit reached with blockers or unverified items;
- tool or environment restriction prevented strict independent review;
- not applicable.

Reviewers report; implementers modify. Do not finalize delivery before resolving blockers.

---

## 8. Definition of Done

A task is complete only when every applicable condition holds:

1. The target problem is handled without scope creep.
2. Code compiles or builds.
3. Minimum targeted validation ran.
4. Regression, compatibility, security, performance, and user experience were checked.
5. No debug code, temporary files, or sensitive information remain.
6. Formal documentation and CHANGELOG follow project conventions.
7. Git diffs are inspected and functional boundaries match commit boundaries.
8. Applicable strict or compatibility review completed and blockers are resolved.
9. Work committed, pushed, deployed, restarted, or stopped at the authorized boundary.
10. Every failure, unverified item, and residual risk is explicit.

If the task explicitly requires strict independent review but tools cannot provide it, report “implementation and validation complete, final quality gate blocked.” Do not claim full completion.

---
