# Reviewer Model Routing and Escalation

## 1. Four Approved Tiers

Automatic reviewers may use only:

| Tier | Model | Reasoning Effort | Typical Work |
|---|---|---|---|
| `luna-low` | `gpt-5.6-luna` | `low` | Search, extraction, classification, checklist verification, and mechanical evidence checks |
| `luna-medium` | `gpt-5.6-luna` | `medium` | Bounded read-only analysis, compatibility scans, and test-evidence review |
| `terra-medium` | `gpt-5.6-terra` | `medium` | Business semantics, multi-file logic, specialist engineering judgment, and ordinary complex review |
| `terra-high` | `gpt-5.6-terra` | `high` | Transactions, concurrency, security, irreversible migrations, core state machines, and blocking adjudication |

Fixed escalation chain:

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

Automatic flows prohibit Sol, `xhigh`, `max`, and `ultra`. `terra-high` is a hard automatic ceiling, not a default.

## 2. Three Independent Tier Systems

| Dimension | Values | Controls |
|---|---|---|
| Execution workflow | `LIGHT / STANDARD / STRICT` | Authorization, validation, rollback, and delivery gates |
| Reviewer cost | `economy / balanced / deep` | Reviewer count, scope, and context budget |
| Model tier | Four approved tiers | Model and reasoning effort for one reviewer |

A strict workflow does not imply high reasoning effort, and `deep` does not mean every reviewer uses `terra-high`.

## 3. Default Mapping

| Cost Tier | Default Model Tier | Default Reviewers |
|---|---|---:|
| `economy` | `luna-low` | 0–1 |
| `balanced` | `luna-medium` | 1–2 |
| `deep` | `terra-medium` | 2–3 |

The coordinator may override a default by role but must record the reason. A high-risk boundary uses at most one `terra-high` reviewer by default; two require explicit authorization or a project rule and must remain within the controller hard limit.

## 4. Selection by Reviewer Role

| Reviewer | Normal Tier | Escalation Condition |
|---|---|---|
| Test and delivery | `luna-low` | `luna-medium` for complex regression scope; normally no Terra High |
| Compatibility and regression | `luna-medium` | `terra-medium` for public APIs, historical data, or coexistence of versions |
| Performance and resources | `luna-medium` | `terra-medium` for SQL, locks, thread pools, capacity, or hot paths; `terra-high` for complex concurrent resource contention |
| Function and business | `terra-medium` | `terra-high` for core state machines, money, inventory, or business-definition conflict |
| Authorization and security | `terra-medium` | `terra-high` for authentication, privilege escalation, tenant isolation, or privileged entry points |
| Data and contracts | `terra-medium` | `terra-high` for transactions, migrations, message success boundaries, or irreversible data changes |
| State and concurrency | `terra-medium` | `terra-high` for races, lock ordering, idempotency, compensation, or complex timing |

## 5. Escalation and Deescalation

Valid escalation evidence:

- the current tier cannot reach an evidence-backed conclusion;
- business semantics or a complex cross-module call chain must be understood;
- valid evidence conflicts;
- transaction, concurrency, security, irreversible migration, or core-state risk is present.

The following alone do not justify escalation: many files, long logs, many skills, long task duration, `STRICT` workflow, or entering round two.

Prefer deescalation or stopping when:

- the subtask is only search, checklist verification, formatting, or evidence extraction;
- existing evidence is enough to decide;
- the same reviewer already reviewed the same packet;
- the previous round passed the same packet without findings;
- broader scope cannot change the gate conclusion.

## 6. Runtime Confirmation

- Reviewer TOML deliberately does not fix `model` or `model_reasoning_effort`, preventing high-priority static configuration from blocking dynamic routing.
- Before dispatch, `review_controller.py` records both the requested tier and `minimum_acceptable_profile`. The minimum defaults to the request, may be lowered explicitly, and may never exceed the request.
- A Reviewer declaration matching the request is `declared_match`; a lower tier at or above the minimum is `fallback_acceptable`; a tier below the minimum is `underpowered`, which may only be recorded as `incomplete` and cannot be merged or closed normally.
- A tier above the request or outside the approved set is `mismatch`. A Reviewer declaration can never produce `verified`; only a future trusted-host adapter may supply that evidence level.
- The controller governs this Skill's dispatch ledger only; it does not replace the Codex platform allowlist. The coordinator must launch each subagent explicitly at the ledger tier.
- A requested model is policy evidence, not proof of the actual runtime model. Without host-attested evidence bound to the dispatch, report runtime model evidence as unavailable and keep any diagnostic observation separate.

## 7. INLINE Decision and Calibration

- When no subagent is needed, append a phase decision with `route --decision INLINE`. It creates no round, increments no Reviewer counter, and consumes no model budget.
- A newly initialized v5 ledger must record `INLINE` or `DELEGATE` before `plan`; ledgers migrated from v4 or earlier retain the decision-free compatibility path.
- While the latest decision is `INLINE`, both `plan` and `dispatch` fail. Before the first round only, a `DELEGATE` redecision may be appended with the previous decision id, a change reason, and new evidence; history is never overwritten.
- Reviewer v3 results contain task difficulty, duration, pending attribution, and versioned estimated cost, and reject fields outside the schema. `calibration_finalized` must be `false` in a Reviewer file. After repair and validation, the primary coordinator finalizes attribution separately with evidence through `finalize-calibration`.
- The controller projects results to `review-results.jsonl` under `task_id + reviewer + result_id` and keeps requested profile, declared runtime profile, runtime evidence level, and cost-basis profile separate. Without trusted-host evidence, the approved requested profile remains the cost basis.
- `validate` checks the projection ledger against `review-state`; after an interrupted write, use `sync-calibration` to rebuild it deterministically from authoritative state.
- `profile-weight-v1` uses weights 1/2/4/8. Missing or invalid cost remains unknown; only controller-finalized records participate in low-yield classification.
