# Git, CHANGELOG, and Final Delivery

## Contents

- 10. Git, CHANGELOG, and Delivery
- 11. Final Delivery Format

## 10. Git, CHANGELOG, and Delivery

### 10.1 Precommit Check

Inspect `git status`, `git diff`, unrelated changes, broad formatting, temporary and log files, debug code, sensitive information, lock files, environment configuration, and external-memory documents.

Without explicit authorization, do not push, create a pull request, merge, or force-push.

### 10.2 Functional Boundaries and Commit Splitting

One independent bug, feature, API adjustment, performance change, security change, compatibility change, or migration normally forms one functional boundary. Independent boundaries should be committed separately.

Combine changes only when all are required to form one buildable and verifiable behavior, and explain why they cannot be separated.

Commit splitting, commit-message correction, and formatting without behavior change are not new functional boundaries.

### 10.3 CHANGELOG

Follow the current project's existing convention, for example:

- one entry per functional commit;
- one entry per pull request;
- release-time maintenance;
- Conventional Commits, Changesets, or automatic generation.

When the project already has `CHANGELOG.md` and the task requires updates by functional boundary, update it before the final commit so content matches actual changes and validation.

Do not:

- substitute CHANGELOG for tests or review;
- record incomplete or unverified work as complete;
- put external task cards, plans, or handoff records into project CHANGELOG;
- create a new CHANGELOG that conflicts with project conventions.

### 10.4 Commit Messages

Prefer the project's existing convention. Otherwise use the requester-approved format; for this repository:

```text
<type> | <Chinese functional summary>
```

Recommended types:

- `feat`: new feature;
- `fix`: bug repair;
- `perf`: performance improvement;
- `refactor`: refactoring without external behavior change;
- `test`: tests;
- `docs`: documentation;
- `chore`: build, tooling, and maintenance;
- `security`: security repair when allowed by the project.

Examples:

```text
fix | 修复视频任务状态回写并补充幂等验证
perf | 优化订单批量查询并验证执行计划
feat | 增加任务取消能力与状态流转验证
```

Do not use summaries such as “optimize code,” “fix issue,” or “update content” that hide the boundary. Do not claim validation that was not performed.

### 10.5 Delivery Order for One Functional Boundary

1. Modify.
2. Run minimum targeted validation.
3. Stabilize the diff.
4. Run independent or compatibility review.
5. Repair blockers.
6. Revalidate and rereview.
7. Update formal documentation or CHANGELOG.
8. Inspect the diff.
9. Create the commit and return the actual hash.
10. Stop, push, or continue to the next boundary according to authorization.

### 10.6 Commit Locally Without Push

After modification, validation, review, documentation, and diff inspection, create a local commit, return its actual hash, then stop. Do not push.

---

## 11. Final Delivery Format

A complex-task report includes as applicable:

### Executive Summary

- project and execution profile;
- goal, actual completion, and incomplete items;
- whether code, configuration, database, or environment changed;
- current commit, push, deployment, restart, and effective states.

### Changes and Validation

- files and key changes;
- actual commands;
- backend tests, frontend builds, workers, exports, migrations, and full-test results;
- failures, relationship to the change, and reasons for omitted checks.

### Independent Review

- gate type;
- reviewer and context;
- diff scope;
- six-dimensional conclusions;
- blocking and non-blocking issues;
- final conclusion.

### Impact and State

- performance, compatibility, security, authorization, experience, and resources;
- CHANGELOG, commit message, and hash;
- production artifact, restart, loaded version, health, and effective functionality as separate levels;
- risks, unverified items, and externally required operations.

Omit inapplicable items, but never omit failures, unverified scope, authorization boundaries, or risks.
