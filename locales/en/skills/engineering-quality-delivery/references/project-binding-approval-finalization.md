# Project Binding, Approval, and Finalization

## 1. Project Binding

For cross-session, nontrivial, or protected-operation tasks, prefer `cp-runtime.py project-onboard` to create outside the repository:

```text
project-profile.json
project-state.json
project-memory.md
```

The Task Envelope binds project ID, repository root, and Profile hash. If any differs, Profile integrity fails, or the repository is replaced, stop protected operations and reconfirm.

## 2. Separate Approval from Evidence

Approval is explicit authorization by the requester or workflow for a specific operation. Evidence records an action or validation result. Neither replaces the other.

Approval for a protected operation binds at least:

- project ID and task ID;
- a specific operation among `commit`, `push`, `deploy`, `restart`, `data-write`, `production-operation`, and `make-effective`;
- `local`, `nonproduction`, or `production` environment;
- current Git baseline fingerprint;
- expiration and single-use status.

Fail closed when baseline, project, task, environment, operation, validity, or consumption state differs. This is workflow control, not a hard Codex-platform or operating-system permission boundary.

## 3. Before/After Protocol

```text
Preflight
  -> Validate Project Binding
  -> Validate and consume Approval
  -> Execute external action
  -> Read back actual current state
  -> Record Action Evidence
  -> Finalization
```

Tools validate, record, and read back. They do not execute Git, deployment-platform, database, or production operations on behalf of those systems.

## 4. Finalization Integrity

Evaluate separately:

```text
modified / validated / reviewed / committed / pushed /
deployed / restarted / effective
```

Each claim requires direct evidence or action readback on the current baseline. Block or remove unsupported claims from the final report. Generate final wording from the accepted design and actual state, not rejected intermediate proposals from full chat history.
