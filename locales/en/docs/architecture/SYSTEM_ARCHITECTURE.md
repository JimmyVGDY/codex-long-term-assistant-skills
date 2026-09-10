# V7.8 Current System Architecture and Security Boundaries

> Status: `active`. This page describes the current V7.8.0 package architecture. Earlier design and release evidence is retained only for historical traceability.

## 1. Layers

```text
Global AGENTS (minimal cross-project rules)
        ↓
10 Skills (4 primary domains + 6 supporting capabilities, loaded on demand)
        ↓
Main Agent / 7 Reviewers
        ↓
Observation / governance: 6 existing Hook events
        ↓
TaskOutcomeEvent V3
        ↓
Project Context Runtime
        ↓
Observation / Assessment / Proposal
        ↓
Human Decision + Independent Implementation Task
```

The package version is V7.8.0. Names such as `TaskOutcomeEvent V3`, Operation v2, and Evolution Policy identify component contracts or data formats; they do not mean an older package is installed.

## 2. Skill routing

Choose one primary domain Skill per phase:

- `backend-engineering`: server applications, APIs, business logic, transactions, concurrency, and workers;
- `frontend-engineering`: browsers, WebViews, renderers, state, and interaction;
- `ai-engineering`: model calls, RAG, agents, evaluation, inference, and multimodal generation;
- `data-middleware-infrastructure`: databases, caches, messaging, search, storage, GPU resources, containers, and networks.

Logging, quality delivery, independent review, technical documentation, long-running memory, and controlled evolution are supporting capabilities loaded by phase. See the [V7.6 domain Skill architecture](../V7_DOMAIN_SKILL_ARCHITECTURE.md) and [V7.6 Skill trigger matrix](../SKILL_TRIGGER_MATRIX.md) for detailed boundaries.

## 3. Project and data isolation

Every TaskOutcomeEvent V3 binds at least:

- `project_id`;
- `repo_fingerprint`;
- `session_id / turn_id / task_id`;
- `event_id`.

Observation first verifies the hash chain or HMAC, checks `project_id + repo_fingerprint`, deduplicates by `event_id`, and then aggregates by Task. A project or repository identity mismatch fails closed instead of mixing cross-project records into one conclusion.

## 4. Hook and model boundaries

`PreToolUse` checks the automatic sub-agent model ceiling before dispatch. `SubagentStart` and `SubagentStop` record minimal runtime facts, while the other observation Hooks form lifecycle events; `Interrupt` remains host-controlled and does not write legacy gate-cancellation state. The Hook guard is a workflow protection, not an unbypassable platform security boundary.

Model evidence keeps three meanings separate:

```ini
dispatch_policy_status = whether the pre-dispatch request obeyed the approved ceiling
host_model_identity = not collected, inferred, persisted, or exported
```

Only the approved dispatch profile, permit, and reserved cost participate in governance. Host runtime model identity and reasoning effort are outside the data contract.

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

- Enter current guidance through the [documentation hub](../README.md), where it is marked V7.6.
- Upgrade-source versions, migration mappings, and component-contract versions may appear in current guidance only when their purpose is explicit.
- Earlier release notes, validation reports, and design documents remain available for traceability but do not establish current installation, runtime, or acceptance state.
- Historical detail pages are excluded from default site search so outdated commands cannot be confused with current operating instructions.

## Optional project gate and effective loading

The registration contains eight entry points, while project gates default to disabled. In V7.8.0, `UserPromptSubmit` is asynchronous observation, `Stop` is neutral observation, and `Interrupt` remains host-controlled. Canonical `apply_patch` advances repository-external Operation v2 through PreToolUse/PostToolUse only for an explicitly enabled policy. A creates an origin and is denied, B atomically binds READY, and completion accepts only B's receipt. Unconfigured or disabled policies remain neutral.

```text
Unconfigured or disabled ───────────────→ native writes preserve host behavior
Legacy enabled + native write tool ────→ deny LEGACY_WRITE_ORIGIN_UNAVAILABLE
UserPromptSubmit / Stop / Interrupt ───→ do not consume legacy GateTask control state
```

Configured `enabled=true`, a loaded Plugin, and semantic suitability are separate conclusions. Legacy `prepare/finish/check` and GateTask v1 receipts cannot authorize Operation v2 writes. An open session can retain an older Plugin snapshot, so verify actual behavior in a fresh task after upgrade. Hook permission and tool side effects are not atomic, and shell/MCP entry points do not have guaranteed pre-write interception.

All 11 Codex CLI versions in the frozen window have per-version official source evidence for UserPromptSubmit async behavior; Desktop and other real hosts still require separate readback. See the [capability index and workflow entry](../CAPABILITY_INDEX.md) for legacy gate enable/disable entry points, but this patch does not restore the legacy task lifecycle as write authorization.
