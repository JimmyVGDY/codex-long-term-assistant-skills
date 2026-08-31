# Custom Agents for Multi-Agent Independent Review

This directory contains seven narrowly scoped Reviewers installed into `${CODEX_HOME:-$HOME/.codex}/agents/`.

| File | Agent Name | Review Dimension | Normal Tier |
|---|---|---|---|
| `cp-review-functional-business.toml` | `cp_review_functional_business` | Functional correctness and business definitions | `terra-medium` |
| `cp-review-compatibility-regression.toml` | `cp_review_compatibility_regression` | Regression and compatibility | `luna-medium` |
| `cp-review-security-access.toml` | `cp_review_security_access` | Authorization and security | `terra-medium` |
| `cp-review-performance-resources.toml` | `cp_review_performance_resources` | Performance and resource burden | `luna-medium` |
| `cp-review-data-contract.toml` | `cp_review_data_contract` | Data and contract consistency | `terra-medium` |
| `cp-review-state-concurrency.toml` | `cp_review_state_concurrency` | State, concurrency, and interaction boundaries | `terra-medium` |
| `cp-review-test-delivery.toml` | `cp_review_test_delivery` | Test evidence and delivery boundaries | `luna-low` |

Reviewer TOML deliberately does **not** set `model` or `model_reasoning_effort`. The coordinating agent chooses dynamically along `luna-low -> luna-medium -> terra-medium -> terra-high`, with Terra High as the automatic ceiling. Fixing a model in TOML could prevent cost deescalation.

Every Reviewer:

- reads the packet summary, diff statistics, and assigned scope first, expanding only when evidence is insufficient;
- does not modify code, tests, documentation, data, or environments, and does not commit, push, deploy, or restart;
- does not spawn more agents;
- merges findings with the same root cause, using at most eight groups by default;
- returns structured checked scope, evidence, unverified items, model runtime state, and isolation level.

## Runtime Boundary

`sandbox_mode = "read-only"` proves configuration intent only. When the parent session is writable and no valid sandbox-denial evidence exists, report only `logical-readonly`. High-risk, production, authorization-security, real-data, and irreversible work should run under an entirely read-only parent session with verified runtime isolation.
