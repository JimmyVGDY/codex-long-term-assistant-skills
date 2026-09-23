# Custom Agents for Multi-Agent Independent Review

This directory contains seven narrowly scoped Reviewers installed into `${CODEX_HOME:-$HOME/.codex}/agents/`.

| File | Agent Name | Review Dimension |
|---|---|---|
| `cp-review-functional-business.toml` | `cp_review_functional_business` | Functional correctness and business definitions |
| `cp-review-compatibility-regression.toml` | `cp_review_compatibility_regression` | Regression and compatibility |
| `cp-review-security-access.toml` | `cp_review_security_access` | Authorization and security |
| `cp-review-performance-resources.toml` | `cp_review_performance_resources` | Performance and resource burden |
| `cp-review-data-contract.toml` | `cp_review_data_contract` | Data and contract consistency |
| `cp-review-state-concurrency.toml` | `cp_review_state_concurrency` | State, concurrency, and interaction boundaries |
| `cp-review-test-delivery.toml` | `cp_review_test_delivery` | Test evidence and delivery boundaries |

Reviewer TOML deliberately does **not** set `model` or `model_reasoning_effort`. The coordinator specifies each tuple under the root's fixed [model and cost policy](../docs/MODEL_ROUTING_AND_COST_POLICY.md): V3 retains frozen scoring; explicit V4 checks scenario qualification, compares effort/model gains, then admits resources. Role names do not predetermine a model. Registered Reviewers stop at Astra High, with no automatic xhigh/max/ultra. Worker/Explorer assignments retain the original four tiers and Terra High ceiling.

Every Reviewer:

- reads the packet summary, diff statistics, and assigned scope first, expanding only when evidence is insufficient;
- does not modify code, tests, documentation, data, or environments, and does not commit, push, deploy, or restart;
- does not spawn more agents;
- merges findings with the same root cause, using at most eight groups by default;
- returns checked scope, evidence, unverified items, the approved model/effort assignment and references, and isolation level; it does not infer or self-report actual host model identity.

## Runtime Boundary

`sandbox_mode = "read-only"` proves configuration intent only. When the parent session is writable and no valid sandbox-denial evidence exists, report only `logical-readonly`. High-risk, production, authorization-security, real-data, and irreversible work should run under an entirely read-only parent session with verified runtime isolation.
