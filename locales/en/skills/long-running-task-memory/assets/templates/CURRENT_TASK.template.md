# Current Task Card

## State Metadata

- State version: 0
- Task ID:
- Created at:
- Last updated at:
- Canonical time zone: Asia/Shanghai
- Last checkpoint ID:
- Current status: Not started
- Current phase:
- Current node:

<!-- live-task-state:begin -->
- Most recently completed node:
- Current blocker: None
- Single next action: Define the first recoverable step
<!-- live-task-state:end -->

## Project and Git Snapshot

- Project / repository:
- Repository path:
- Current branch:
- Baseline Commit:
- Current HEAD:
- `git status --short` summary:
- `git diff --stat` summary:
- Untracked files:
- Workspace fingerprint:
- Validation-baseline fingerprint:
- Workspace matches last checkpoint: Unverified

## Execution Mode and Authorization

- [ ] Analysis
- [ ] Local modification
- [ ] Non-production environment operation
- [ ] Production environment operation
- Allowed changes:
- Prohibited changes:
- Commit authorized:
- Push authorized:
- Deployment authorized:
- Restart authorized:
- Database / Redis / MQ / file writes authorized:
- Staged rollout, rollback, and stop conditions:

## Goals and Non-Goals

- Goals:
- Out of scope:
- Acceptance criteria:

## Known Facts and Evidence

- Reported symptom:
- Confirmed facts:
- High-probability conclusions:
- Hypotheses:
- Unverified:

## Plan and Validation

- Current plan version:
- Minimum targeted validation:
- Completed validation:
- Invalidated validation that must be rerun:

## Checkpoint Status

- Completed nodes not yet persisted: 0
- Substantive actions since last checkpoint: 0 / 8
- Checkpoints loaded during recovery: 3
- Active checkpoint limit: 20
- Shared-memory writer: Coordinating Agent

## Multi-Agent Review Status

- Required:
- Current gate: system-isolated review / behaviorally read-only review / implementer self-review / not applicable
- Actual parent-session sandbox: read-only / workspace-write / danger-full-access / unknown
- Reviewer TOML declaration:
- Runtime isolation level: system-readonly / logical-readonly / self-review / unknown
- Strict read-only review selected:
- Eligible for strict read-only review:
- Isolation-evidence path:
- Current review round / default maximum: 0 / 2
- Current logical depth / default maximum: 0 / 2
- Reviewers used / default total ceiling: 0 / 6
- Current parallel Reviewers / default ceiling: 0 / 3
- Centralized repair round / default maximum: 0 / 2
- Current blocking findings:
- Review-ledger path:

## Required Checks Before Recovery

1. Current request and authorization;
2. branch, HEAD, workspace fingerprint, and untracked files;
3. the three most recent checkpoints;
4. core code, configuration, and tests involved in the next action;
5. whether validation evidence still matches the current workspace;
6. conflicts between documentation and actual state.
