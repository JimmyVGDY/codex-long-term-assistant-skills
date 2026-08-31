# Repository Isolation, Minimization, Security, Retention, and Archiving

## Contents

- 13. Strict Separation from the Project Repository
- 14. Content Minimization and Security
- 15. External-Memory Security and Lifecycle Governance
- 16. Archiving
- 17. Document Maintenance Does Not Prove Task Completion

## 13. Strict Separation from the Project Repository

External memory:

- belongs only in an agent-specific directory;
- must not be placed in the project repository;
- must not be staged, committed, or pushed;
- must not be written into the project CHANGELOG;
- must not be placed in the repository and hidden with `.gitignore` as a workaround;
- must not be delivered as formal team engineering documentation.

| Type | Storage Location | Enters Git | Purpose |
|---|---|---:|---|
| Project CHANGELOG | Project repository | Yes | Formal feature and version changes |
| Architecture, API, and deployment documentation | Existing project directories | Per project rules | Team engineering documentation |
| External agent memory | Agent-specific directory | No | Recovery, plans, progress, and review |
| DELIVERY_RECORD | Agent-specific directory | No | Agent task-level delivery record |

Before committing, confirm that external memory has not entered Git accidentally.

---

## 14. Content Minimization and Security

Prefer retaining:

- goals, scope, and authorization;
- confirmed facts and evidence levels;
- modified files and important symbols;
- actual commands and validation summaries;
- reviews, issue ledgers, and decisions;
- current blockers, risks, and next action.

Avoid:

- complete conversations and internal reasoning;
- large source excerpts, complete logs, and irrelevant tool output;
- repeated descriptions;
- stale speculation and subjective conclusions;
- passwords, tokens, keys, cookies, private data, and confidential organizational information.

Reference paths to logs, test reports, and reviewer reports rather than copying them in full.

---

## 15. External-Memory Security and Lifecycle Governance

### 15.1 Minimum Sensitive Information

External memory records only the minimum facts and evidence index required to resume work. Never write:

- plaintext passwords, tokens, cookies, access keys, secret keys, or private keys;
- complete database, Redis, message-queue, object-storage, or production connection strings;
- full identity numbers, phone numbers, bank-card data, addresses, or personal information;
- large raw production logs, complete request or response bodies, model input or output, or message bodies;
- unnecessary internal domains, IP addresses, accounts, or directory topology.

When correlation is required, use a stable redacted identifier such as `<TOKEN_REDACTED>` or `user-***1234`, and store only the evidence-file path, time window, and minimum summary.

### 15.2 Permissions and Local Isolation

- On Linux or WSL, use directory mode `700` for `<AGENT_CONTEXT_ROOT>` and mode `600` for document and JSON state files where possible.
- On Windows, inspect ACLs so other ordinary accounts cannot read the data.
- Do not store external memory in shared temporary directories, project repositories, container image layers, or public network shares.
- Do not synchronize it by default to OneDrive, NAS, personal cloud storage, or cross-device tools. Any synchronization must follow organizational data-classification and encryption policies.
- Reviewers and subagents do not receive write access to shared memory.

Optional commands:

```text
checkpoint.py security-check
checkpoint.py secure
```

`security-check` recognizes common credential patterns only; it does not replace human redaction or organizational DLP. The script cannot configure Windows ACLs consistently, so local policy must verify them.

### 15.3 Retention

Recommended defaults:

```text
DEFAULT_COMPLETED_TASK_RETENTION_DAYS = 90
DEFAULT_TEMPORARY_ANALYSIS_RETENTION_DAYS = 30
```

Use stricter project, organizational, or regulatory requirements when they apply. Records involving production incidents, privacy, or security events must follow organizational policy rather than a generic duration.

`retention-report` lists archive candidates past retention; it never deletes automatically. Deletion, migration, compression, and backup are separately authorized actions.

### 15.4 Lifecycle States

At archive time, mark each task as:

- active;
- complete, observation pending;
- complete and ready to archive;
- rolled back;
- cancelled;
- retention candidate;
- retained for regulation or audit.

Reaching a default age never permits deletion of a record still referenced by a project, audit, incident review, or legal hold.

---

## 16. Archiving

After task completion:

- retain stable facts in `PROJECT_CONTEXT.md`;
- retain valid decisions in `DECISIONS.md`;
- continue maintaining `DELIVERY_RECORD.md`;
- clear, switch, or archive `CURRENT_TASK.md`;
- archive `PLAN.md`, `PROGRESS.md`, `HANDOFF.md`, and `reviews/` under:

```text
archive/<task-id>/
```

- update resolved items in `KNOWN_ISSUES.md` rather than deleting them silently;
- mark the task complete in `HANDOFF.md` so it cannot be mistaken for current state.

Do not delete existing local documents without authorization.

---

## 17. Document Maintenance Does Not Prove Completion

None of the following alone proves task completion:

- updating `CURRENT_TASK` or `PROGRESS`;
- changing plan state to complete;
- creating `HANDOFF`;
- stating in a document that tests or review passed;
- writing “fixed” in CHANGELOG;
- having a summary in Codex Memories.

Completion still depends on actual code, builds, targeted tests, reviews, runtime results, Git state, and acceptance evidence.
