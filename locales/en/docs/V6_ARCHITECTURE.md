# V6 Architecture and Security Boundaries

## 1. Layers

```text
Global AGENTS (minimum cross-project rules)
        ->
10 Skills (progressive loading)
        ->
Main Agent / 7 Reviewers
        ->
Lifecycle Hooks
        ->
TaskOutcomeEvent V2
        ->
Project Context Runtime
        ->
Observation / Assessment / Proposal
        ->
Human Decision + Independent Implementation Task
```

## 2. Data Isolation

Every V2 event binds at least:

- `project_id`;
- `repo_fingerprint`;
- `session_id / turn_id / task_id`;
- `event_id`.

Observation first validates the hash chain and HMAC, then project/repository binding, then deduplicates, then aggregates by task. A cross-project or cross-repository record cannot be ignored while continuing the same conclusion; it fails the current observation closed.

## 3. Hook Permissions

PreToolUse applies a guard before automatic subagent requests exceed the model ceiling. Failures in other observational Hooks do not normally block ordinary development. A Hook guard is still not an unbypassable platform boundary, so actual SubagentStart runtime data forms a second layer of detection evidence when the host attests it.

## 4. Privacy

Lifecycle logs retain governance metadata only. Fields resembling prompt, content, message, response, patch, diff, code, token, secret, authorization, cookie, API key, or private key are redacted by default.

## 5. Proposal Permission Model

A Proposal is governance advice only:

```text
PENDING_REVIEW
  ├─ REJECTED
  ├─ DEFERRED
  └─ ACCEPTED
       ->
IMPLEMENTATION_LINKED
       ->
VALIDATION_RECORDED
       ->
CLOSED
```

A replaced proposal may become `SUPERSEDED`. No state changes `execution_authorization` from `NONE`.
