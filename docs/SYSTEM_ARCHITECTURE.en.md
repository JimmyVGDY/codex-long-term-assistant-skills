# V7.4 Current System Architecture and Security Boundaries

> Status: `active`. This page describes the current V7.4.1 package architecture. Earlier design and release evidence is retained only for historical traceability.

## 1. Layers

```text
Global AGENTS (minimal cross-project rules)
        ↓
10 Skills (4 primary domains + 6 supporting capabilities, loaded on demand)
        ↓
Main Agent / 7 Reviewers
        ↓
6 Lifecycle Hooks
        ↓
TaskOutcomeEvent V2
        ↓
Project Context Runtime
        ↓
Observation / Assessment / Proposal
        ↓
Human Decision + Independent Implementation Task
```

The package version is V7.4.1. Names such as `TaskOutcomeEvent V2` and Evolution Policy identify component contracts or data formats; they do not mean an older package is installed.

## 2. Skill routing

Choose one primary domain Skill per phase:

- `backend-engineering`: server applications, APIs, business logic, transactions, concurrency, and workers;
- `frontend-engineering`: browsers, WebViews, renderers, state, and interaction;
- `ai-engineering`: model calls, RAG, agents, evaluation, inference, and multimodal generation;
- `data-middleware-infrastructure`: databases, caches, messaging, search, storage, GPU resources, containers, and networks.

Logging, quality delivery, independent review, technical documentation, long-running memory, and controlled evolution are supporting capabilities loaded by phase. See the [V7.4 domain Skill architecture](V7_DOMAIN_SKILL_ARCHITECTURE.md) and [V7.4 Skill trigger matrix](SKILL_TRIGGER_MATRIX.md) for detailed boundaries.

## 3. Project and data isolation

Every TaskOutcomeEvent V2 binds at least:

- `project_id`;
- `repo_fingerprint`;
- `session_id / turn_id / task_id`;
- `event_id`.

Observation first verifies the hash chain or HMAC, checks `project_id + repo_fingerprint`, deduplicates by `event_id`, and then aggregates by Task. A project or repository identity mismatch fails closed instead of mixing cross-project records into one conclusion.

## 4. Hook and model boundaries

`PreToolUse` checks the automatic sub-agent model ceiling before dispatch. `SubagentStart` and `SubagentStop` record minimal runtime facts, while the remaining Hooks form lifecycle events. The Hook guard is a workflow protection, not an unbypassable platform security boundary.

Model evidence keeps three meanings separate:

```ini
requested_model_policy = whether the requested configuration obeyed the ceiling
runtime_model_evidence = whether the host supplied trusted actual-model evidence
diagnostic_model_observation = diagnostic context only
```

Requesting Luna or Terra does not prove which model actually ran. Without a trusted host anchor, `runtime_model_evidence` remains `UNAVAILABLE`.

## 5. Reviewer isolation

`read-only` in a Reviewer TOML file expresses configuration intent only. If the parent session is writable and no valid system-denial evidence exists, the review is only `logical-readonly`. It can be `system-readonly` only when the whole parent session is read-only or a controlled probe is actually denied by the system. Self-review is not independent review.

## 6. Privacy and integrity

Lifecycle data retains only minimal structured metadata required for governance. Raw prompts, complete responses, source bodies, patches, diffs, tokens, secrets, authorization data, cookies, API keys, and private keys must not be persisted by default.

The event chain uses forward SHA-256 integrity and can add HMAC and detached seals when configured. The SessionEnd Hook only constructs a capped, body-free sanitized event and dispatches without waiting; it performs no event-chain I/O or synchronous pipe write. A detached worker validates stable lifecycle identity at the shared queue boundary, semantically deduplicates and persists the event, then seals the chain through a v2 signed job bound to `event_id`. Evolution rejects an unsealed `seal_required` tail. Active events, read-only segments, and archive manifests preserve project identity and chain-head continuity; corruption, cross-project leakage, or inconsistent references fail closed.

## 7. Proposal authorization model

A Proposal is governance advice only:

```text
PENDING_REVIEW
  ├─ REJECTED
  ├─ DEFERRED
  └─ ACCEPTED
       ↓
IMPLEMENTATION_LINKED
       ↓
VALIDATION_RECORDED
       ↓
CLOSED
```

A proposal superseded by newer evidence may become `SUPERSEDED`. No state changes `execution_authorization` from `NONE`. Human acceptance still requires a new implementation task and fresh authorization for modifications, commits, pushes, or publication.

## 8. Current and historical documentation

- Enter current guidance through the [documentation hub](README.md), where it is marked V7.4.
- Upgrade-source versions, migration mappings, and component-contract versions may appear in current guidance only when their purpose is explicit.
- Earlier release notes, validation reports, and design documents remain available for traceability but do not establish current installation, runtime, or acceptance state.
- Historical detail pages are excluded from default site search so outdated commands cannot be confused with current operating instructions.
