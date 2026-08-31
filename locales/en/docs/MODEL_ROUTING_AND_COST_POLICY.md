# Subagent Model Tiers and Cost Policy

## 1. Goal

Preserve independent contexts, specialist review, and critical-risk judgment while reducing unnecessary subagents, duplicated context, repeated scans, and high reasoning effort.

This policy governs only subagents launched automatically by this package. The main agent keeps its selected model. Agents launched manually outside this workflow are not blocked by `review_controller.py`.

## 2. Three Non-Equivalent Dimensions

| Dimension | Values | Controls |
|---|---|---|
| Execution workflow | `LIGHT / STANDARD / STRICT` | Authorization, validation, rollback, and delivery gates |
| Reviewer cost | `economy / balanced / deep` | Reviewer count, scope, context, and rounds |
| Model tier | `luna-low / luna-medium / terra-medium / terra-high` | Model and reasoning effort |

`STRICT` does not imply `terra-high`, and `deep` does not mean every Reviewer uses High.

## 3. Four Model Tiers

| Tier | Model | Reasoning Effort | Typical Work |
|---|---|---|---|
| `luna-low` | `gpt-5.6-luna` | `low` | File/symbol location, extraction, classification, formatting, and mechanical state/test checks |
| `luna-medium` | `gpt-5.6-luna` | `medium` | Bounded log classification, ordinary compatibility scans, test-evidence review, and scoped read-only analysis |
| `terra-medium` | `gpt-5.6-terra` | `medium` | Business semantics, multi-file call chains, ordinary implementation, specialist review, and synthesis |
| `terra-high` | `gpt-5.6-terra` | `high` | Complex transactions, races, privilege escalation, irreversible migration, core state machines, and conflict adjudication |

Fixed automatic escalation:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic flows prohibit `gpt-5.6-sol`, `xhigh`, `max`, and `ultra`. The automatic ceiling is `terra-high`.

## 4. Escalation and Deescalation

### 4.1 Escalation Is Allowed When

- Luna cannot reach an evidence-backed conclusion.
- Business definitions or a multi-file call chain must be understood.
- Valid evidence or Reviewer conclusions conflict.
- Transactions, locks, concurrency, idempotency, authorization, migration, or irreversible operations are involved.
- Failure cost clearly exceeds escalation cost.

### 4.2 These Alone Do Not Justify Escalation

- Many files or long logs.
- Many Skills.
- Long task duration.
- `STRICT` workflow.
- A second or third round.
- A parent agent using Terra High.

### 4.3 Prefer Deescalation

- Use Luna for evidence extraction, test-output summaries, and state checks.
- When a postrepair rereview is narrower than round one, keep or lower the tier.
- An actual approved tier below the request is `fallback`, not a violation.
- An actual tier above the request or outside the four approved tiers is `mismatch` and must be acknowledged before closure.

## 5. Default Reviewer Routing

| Reviewer | Default | Escalation Condition |
|---|---|---|
| Test and delivery | `luna-low` | `luna-medium` for complex regression scope |
| Regression and compatibility | `luna-medium` | `terra-medium` for public APIs, historical data, and coexistence |
| Performance and resources | `luna-medium` | `terra-medium` or `terra-high` for complex SQL, locks, thread pools, or capacity |
| Function and business | `terra-medium` | `terra-high` for core state, money, or complex business definitions |
| Authorization and security | `terra-medium` | `terra-high` for authentication, privilege escalation, tenant isolation, or high-impact vulnerabilities |
| Data and contracts | `terra-medium` | `terra-high` for migrations, transactions, message success boundaries, or irreversible change |
| State and concurrency | `terra-medium` | `terra-high` for races, lock ordering, idempotency, compensation, or recovery |

Use at most one `terra-high` Reviewer per boundary by default; the hard ceiling is two after explicit relaxation.

## 6. Cost-Tier Mapping

| Reviewer Tier | Default Model | Reviewers | Notes |
|---|---|---:|---|
| `economy` | `luna-low` | 0–1 | Prefer no subagent for a small task |
| `balanced` | `luna-medium` | 1–2 | One may use `terra-medium` when business judgment is needed |
| `deep` | `terra-medium` | 2–3 | Use `terra-high` only for a critical dimension |

This is a default mapping, not a requirement that every Reviewer in one round use the same tier. Select independently by unique responsibility.

## 7. Configuration and Priority

Recommended low-cost fallback in existing `config.toml`:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

Keep the Codex default `agents.interrupt_message = true`. Disabling it saves little interrupt context but may reduce semantic completeness during recovery.

Specialist Reviewer TOML deliberately omits `model` and `model_reasoning_effort` so the coordinator can choose dynamically. A fixed model in Agent TOML overrides spawn settings and `[agents]` defaults and prevents deescalation.

## 8. Auditability

`review_controller.py dispatch` records:

- requested tier, model, and reasoning effort;
- reason for `terra-high` escalation;
- reason for redispatch against the same packet;
- current isolation level and packet hash.

Reviewer results record runtime model when trustworthy evidence can confirm it and one state:

- `confirmed`: matches the request;
- `fallback`: lower approved tier;
- `unverified`: runtime information cannot be confirmed;
- `mismatch`: above the request, outside Luna/Terra, or an unapproved combination.

The controller governs registered automatic dispatches only. It cannot stop a manually launched higher model outside the workflow. Final reports must state this boundary accurately.
