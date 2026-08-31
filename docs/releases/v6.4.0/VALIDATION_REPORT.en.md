# Codex Cross-Project Long-Term Engineering Assistant V6.4 Validation Report

## Subject

- Version: 6.4.0
- Target host: native Windows Codex CLI 0.150.1
- Recommended form: account-level Plugin
- Upgrade baselines: 6.1.0, 6.2.0, and 6.3.0
- Event contract: TaskOutcomeEvent 2.0
- Automatic subagent ceiling: `gpt-5.6-terra + high`
- Execution authorization: `NONE`

## Candidate-Package Validation

| Check | Result | Evidence Entry |
|---|---|---|
| Package unit and regression tests | PASS, 67/67 | `python -m unittest discover -s tests -v` |
| Shared runtime regressions | PASS, 6/6 | `python -m unittest discover -s runtime/tests -v` |
| Neutral language and structural semantics | PASS | `scripts/semantic-lint.py` |
| Nested Reparse protection in managed trees | PASS | `test_nested_reparse_inside_managed_plugin_tree_is_rejected` |
| Hard-crash Plugin recovery | PASS | `tests/test_package_manager_security.py` |
| Partial-event recovery and cross-segment continuity | PASS | `tests/test_v64_resilience.py` |
| Fail-closed invalid terminal outcome and schema | PASS | `tests/test_v64_resilience.py` |
| Exact `actual_model` allowlist | PASS | `tests/test_v64_resilience.py` |
| Unified release-validator contract | PASS | `tests/test_v64_release.py` |
| Deterministic ZIP and attestation contract | PASS | `tests/test_v64_release_delivery.py` |
| Correlated host-session acceptance without Hook model fields | PASS | `test_lifecycle_uses_correlated_host_session_model_without_rewriting_hook_facts` |

The complete package suite ran on 2026-08-28 with 67 tests; the runtime suite had six. Formal machine evidence records actual command output and duration.

## Independent Review

Two preimplementation Reviewers covered state/concurrency and compatibility/regression. In postimplementation round one, security and test/delivery Reviewers found three blockers and one nonblocking issue:

- Explicit invalid terminal outcomes must not degrade to UNKNOWN.
- Existing events with valid hashes but invalid schemas must be rejected.
- `actual_model` must use an exact allowlist.
- Link-like descendants inside managed trees must be rejected before recursive operations.

All four were repaired with regressions. Round two reused a newly frozen packet for targeted rereview; every original finding closed with no residual finding. Reviewer isolation was `logical-readonly`. Actual model and reasoning effort for round two were not confirmed by host evidence and remained unverified.

## Formal Artifact and Host State

Before formal ZIP construction and real-account upgrade, these remained unverified:

| Check | Result |
|---|---|
| Byte-identical double clean build | NOT_EXECUTED |
| Formal ZIP SHA-256 | NOT_EXECUTED |
| Real-account V6.3 -> V6.4 upgrade | NOT_EXECUTED |
| Plugin installed/enabled/version=6.4.0 | NOT_EXECUTED |
| ZIP/Marketplace/cache payload digests agree | NOT_EXECUTED |
| Ten Skills, seven Reviewers, six Hooks discovered | NOT_EXECUTED |
| Five-event lifecycle in a new session | NOT_EXECUTED |
| SessionEnd three-second compatibility | NOT_EXECUTED |
| External unified validation and attestation | NOT_EXECUTED |

Update this report only after those evidence sources exist. Plans, source presence, or copied files do not replace real host readback.

## Security Boundaries

- Unknown account assets are not deleted.
- `config.toml` and main-agent model configuration are not rewritten.
- Reviewer models are not fixed in TOML.
- Skills, Reviewers, routing, and business repositories are not modified automatically.
- Evolution Proposals are not accepted or implemented automatically.
- Commit, push, deploy, restart, and production operations are not automatic.
- Project aggregation validates both `project_id + repo_fingerprint`.
- Historical Events, Snapshots, Assessments, Proposals, and upgrade backups remain preserved.
