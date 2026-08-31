# V6.6.1 Operating Guide

Chinese: [`USER_GUIDE_V6.6.1.md`](USER_GUIDE_V6.6.1.md)

## Skill entry points

Ten Skills load progressively from task context and remain directly invocable with `$skill-name`: Java, Python backend and AI, frontend, data and infrastructure, observability, engineering delivery, independent review, technical documentation, long-running memory, and controlled evolution governance.

## Reviewer model policy

Reviewer TOML files intentionally omit model and reasoning-effort values. The coordinating flow selects a bounded profile:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic dispatch cannot exceed Terra High. Main-agent configuration is unchanged.

## Runtime model evidence

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

The diagnostic observation cannot be promoted to runtime proof. `runtime_model_evidence=VERIFIED` is valid only when a trusted, fresh, correlatable host attestation reaches the matching Hook.

## Observation lifecycle

```text
TURN_OPENED -> SUBAGENT_STARTED -> SUBAGENT_STOPPED -> TASK_COMPLETED -> SESSION_ENDED
```

Events use TaskOutcomeEvent 2.0, deduplicate by `event_id`, aggregate by `task_id`, isolate by `project_id + repo_fingerprint`, and maintain a hash chain. SessionEnd enqueues a signed job within the Hook budget; a detached worker appends and seals later.

Only minimal metadata is recorded. Raw prompts, full answers, source bodies, patches, tokens, cookies, API keys, and credentials are excluded.

## Controlled evolution

Snapshots and assessments may produce proposals only after evidence gates pass. Every proposal retains `execution_authorization=NONE`. `ACCEPT` permits a separate implementation task; it never authorizes automatic changes, Git actions, deployment, restart, production operation, or data write.
