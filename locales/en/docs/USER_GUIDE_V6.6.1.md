# V6.6.1 Operating Guide

## Activation

The package supplies ten Skills. Codex loads the matching Skill progressively from task context; direct invocation with `$skill-name` remains available when a specific route is intended. Reviewer agents are separate definitions and remain logically read-only.

Typical routes:

- Java and JVM work: `$java-backend-engineering`
- Python backend and AI services: `$python-backend-ai-engineering`
- Browser and renderer work: `$frontend-engineering`
- Databases, Redis, messaging, storage, GPU, containers, and networks: `$data-middleware-ai-infrastructure`
- Logs, metrics, traces, and profiles: `$log-observability-analysis`
- Behavior changes and delivery gates: `$engineering-quality-delivery`
- Independent risk-based review: `$multi-agent-independent-review`
- Formal technical documents: `$technical-document-writing`
- Cross-session recovery: `$long-running-task-memory`
- Cross-task retrospective and proposal governance: `$controlled-evolution-governance`

## Review model policy

Reviewer TOML files intentionally omit model and reasoning-effort values. The coordinating flow selects a bounded profile:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch cannot exceed Terra High. Main-agent configuration is unchanged.

## Runtime model evidence

Three fields remain independent:

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

The third field is diagnostic context only. It cannot be promoted to verified runtime evidence. `runtime_model_evidence=VERIFIED` is valid only when a trusted, fresh, correlatable host attestation reaches the matching Hook.

## Observation lifecycle

```text
TURN_OPENED -> SUBAGENT_STARTED -> SUBAGENT_STOPPED -> TASK_COMPLETED -> SESSION_ENDED
```

Events use TaskOutcomeEvent 2.0, deduplicate by `event_id`, aggregate by `task_id`, isolate by `project_id + repo_fingerprint`, and maintain a hash chain. SessionEnd enqueues a signed job within the Hook budget; a detached worker appends and seals later.

Only minimal metadata is recorded. Raw prompts, full answers, source bodies, patches, tokens, cookies, API keys, and credentials are excluded.

## Controlled evolution

Snapshots and assessments may produce proposals only after evidence gates pass. Every proposal retains `execution_authorization=NONE`. A decision of `ACCEPT` permits a separate implementation task; it never authorizes automatic changes, Git actions, deployment, restart, production operation, or data write.
