# Task Handoff and Recovery Snapshot

## State Metadata

- Project / task / ID:
- Updated at:
- State version:
- Last checkpoint ID:
- Current phase / node:
- Current execution mode:

## Git and Workspace

- Repository path:
- Current branch:
- Baseline Commit:
- Current HEAD:
- Workspace-status summary:
- Untracked files:
- Matches last checkpoint:

## Current Goals and Authorization

- Goals:
- Non-goals:
- Allowed scope:
- Prohibited scope:
- Commit / push / deployment / restart / data-write authorization:

## Current State

- Complete:
- In progress:
- Incomplete:
- Blocked:
- Unverified:

## Recent Checkpoints

| Checkpoint | Node | Result | Next Step |
|---|---|---|---|
|  |  |  |  |

## Multi-Agent Review

- Current round / depth:
- Actual parent-session sandbox:
- Runtime isolation level:
- Eligible for strict read-only review:
- Isolation evidence:
- Reviewers used / ceiling:
- Running Reviewers:
- Completed report paths:
- Consolidation ledger:
- Blocking findings:
- Centralized repair round:

## Completed Validation

| Item | Command / Method | Result | Evidence | Still Valid |
|---|---|---|---|---|
|  |  |  |  |  |

## Failed Attempts and Key Decisions

-

## Required First Steps After Recovery

1. Read the current request and authorization.
2. Read `CURRENT_TASK.md`, the current `PLAN.md`, and the three most recent checkpoints.
3. Verify branch, HEAD, `git status`, `git diff`, and untracked files.
4. Read related ADRs and Reviewer reports.
5. Reread the code, configuration, and tests involved in the next action.
6. If state conflicts are found, write a "state divergence checkpoint" before making further changes.

## Single Next Action

-

## Stop Conditions

-
