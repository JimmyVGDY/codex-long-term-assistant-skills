# Triggers, Risk Levels, and Reviewer Responsibilities

## 1. Trigger Decision

Normally trigger review for:

- behavior changes to public APIs, shared components, databases, caches, messages, serialization, or authorization;
- core business, money, inventory, production, historical compatibility, high-concurrency, or consistency paths;
- medium- or high-risk changes to workers, schedulers, scripts, exports, or data processing;
- critical risks that minimum validation by the coordinating agent cannot cover or that benefit from independent judgment.

Normally do not trigger for:

- commit splitting, commit messages, punctuation, layout, or documentation without behavioral changes;
- short read-only analysis without code changes;
- a low-risk single-file repair with direct test evidence and no shared contract;
- repeating an equivalent check solely to create the appearance of multi-agent work.

## 2. Risk and Default Scale

| Risk | Typical Case | Default Reviewers | Default Cost Tier |
|---|---|---:|---|
| Low | Local, infrequent, no shared contract | 0–1 | `economy` |
| Medium | Single-module business change or ordinary database/asynchronous path | 1–2 | `balanced` |
| High | Cross-module, shared component, authorization, concurrency, or compatibility | 2–3 | `deep` |
| Critical | Production, money, irreversible migration, or core state machine | 3 in round one; 1–2 targeted later | `deep` |

Defaults are cost budgets, not minimum quality levels. Choose reviewers for genuinely independent risk dimensions rather than filling a quota.

## 3. Specialist Reviewers

| Reviewer | Primary Responsibility | Normal Model Tier |
|---|---|---|
| `cp_review_functional_business` | Target problem, business definitions, state transitions, exceptions, and compensation | `terra-medium` |
| `cp_review_compatibility_regression` | Existing paths, legacy APIs and data, shared components, and version coexistence | `luna-medium` |
| `cp_review_security_access` | Authentication, authorization, privilege escalation, tenants, injection, files, and sensitive information | `terra-medium` |
| `cp_review_performance_resources` | SQL, I/O, connections, threads, queues, memory, token/GPU cost, and scalability | `luna-medium` |
| `cp_review_data_contract` | Databases, APIs, Redis, message queues, serialization, and success boundaries | `terra-medium` |
| `cp_review_state_concurrency` | Races, idempotency, timeouts, retries, cancellation, recovery, and interaction state | `terra-medium` |
| `cp_review_test_delivery` | Minimum validation, test gaps, failures, documentation, commits, and authorization | `luna-low` |

Escalate only under the evidence conditions in `reviewer-model-routing.md`. No automatic reviewer may exceed `terra-high`.

## 4. Responsibility Deduplication

- When one issue spans function and data, choose one reviewer by root cause; the other reviews only its independent boundary.
- The test-delivery reviewer reports missing tests. Other reviewers mention a test gap only when it directly prevents validation of their specialist conclusion.
- Assign “high-frequency SQL causes lock contention” to either performance or data as primary owner; state/concurrency adds only independent timing risk.
- Use second opinions only for blocking conflicts, never as a routine way to increase coverage.
