# Project-Level AGENTS.md Example

> Fill this in with facts from the current project, then place it in the repository root. Do not duplicate general global rules. Record only project-specific facts, commands, boundaries, and override values.

## Project Information

- Project name:
- Repository path:
- Technology stack and versions:
- Build command:
- Targeted backend test command:
- Production frontend build command:
- Local startup command:
- Deployment method:
- Canonical technical-document directory:
- Document naming and versioning conventions:

## Project Boundaries

- Permitted modifications:
- Prohibited modifications:
- Backward-compatibility constraints:
- Databases and middleware:
- Current account scale and performance targets:
- Core business success boundary:

## Git and Delivery

- Default branch:
- Commit-message format:
- Feature-boundary and commit-splitting rules:
- CHANGELOG conventions:
- Rules for updating API, database, deployment, and architecture documentation:
- Whether branch creation is permitted:
- Push, deployment, and restart are prohibited by default unless the current task explicitly authorizes them.

## Multi-Agent Review

- Default risk level:
- Required reviewers:
- Reviewers that may be waived:
- Maximum parallel reviewers (must not exceed platform and global limits):
- Maximum review rounds:
- Maximum consolidated-repair rounds:
- Whether critical features require strict independent review:
- Whether strict review uses a system-read-only parent session:
- Minimum acceptable isolation level: system-readonly / logical-readonly
- Location for reviewer runtime-isolation evidence:

## External Memory for Long-Running Tasks

- `<AGENT_CONTEXT_ROOT>`:
- Project identifier:
- External memory must remain outside the repository: yes
- Update `CURRENT_TASK.md` and `PROGRESS.md` at every recoverable checkpoint: yes
- Maximum number of consecutive substantive actions between checkpoints:
- Number of recent checkpoints to read during recovery:
- Shared-memory writer: primary coordinating agent

## Project-Specific Rules

-
