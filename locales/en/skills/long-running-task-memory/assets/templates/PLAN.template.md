# Implementation Plan

## Basic Information

- Project / task:
- Task ID:
- Plan version:
- Status:
- Execution mode:
- Branch / baseline Commit:
- Most recent checkpoint:

## Goals, Non-Goals, and Scope

- Goals:
- Non-goals:
- Change scope:
- Prohibited scope:

## Prerequisites

- [ ] Project and versions confirmed
- [ ] Authorization confirmed
- [ ] Contracts and compatibility confirmed
- [ ] Minimum validation confirmed
- [ ] Multi-Agent review gate and budget confirmed
- [ ] Git / CHANGELOG requirements confirmed
- [ ] Deployment / restart authorized separately
- [ ] Rollback and stop conditions confirmed
- [ ] External-memory directory and single writer confirmed

## Checkpoint Strategy

- After every recoverable step: update `PROGRESS.md` and `CURRENT_TASK.md`
- Maximum consecutive substantive actions: 5
- High-risk operation: checkpoint before and after
- Checkpoints loaded during recovery: 5
- Active checkpoint limit: 20

## Implementation Phases

| Phase | Work | Status | Dependencies | Checkpoint Trigger | Validation | Review | Rollback Point |
|---|---|---|---|---|---|---|---|
| A1 |  | Not started |  |  |  |  |  |

Status: Not started / In progress / Complete / Blocked / Cancelled / Rolled back

## Detailed Steps

### A1: Phase Name

- Objective:
- Input:
- Operation:
- Output:
- Step decomposition:
- Validation:
- Reviewer combination:
- Risks:
- Stop conditions:
- Rollback:

## Multi-Agent Review Isolation and Budget

- Target parent-session sandbox:
- Minimum acceptable isolation:
- Strict read-only review selected:
- Isolation-evidence plan:
- Behaviorally read-only review acceptable:

- Default maximum depth: 2
- Default maximum review rounds: 2
- Default maximum parallel Reviewers: 3
- Default total Reviewer ceiling: 6
- Default maximum centralized repair rounds: 2
- Default Terra High Reviewer ceiling: 1

## Risks and Acceptance

| Risk | Probability | Impact | Control | Rollback |
|---|---|---|---|---|
|  |  |  |  |  |

- Functionality:
- Performance:
- Compatibility:
- Security:
- User experience:
- Feature boundary:
- CHANGELOG:
- Commit / push / target branch:
