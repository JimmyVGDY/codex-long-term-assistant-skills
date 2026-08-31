# V6.0 Release Notes — Deterministic Observation and Plugin Architecture

## Release Objective

V6.0 does not expand permission for automatic self-modification. It improves **observational determinism, evidence integrity, project isolation, cost controls, and human-governed evolution**.

## Key Changes

1. The account-level Skill directory is corrected to `$HOME/.agents/skills`; repository-level Skills remain under `$REPO_ROOT/.agents/skills`.
2. Added the Plugin manifest and six Hook types while retaining standalone and repository compatibility modes.
3. Added `TaskOutcomeEvent V2`. All counters must be non-negative. Records are redacted by default and never store the original prompt, response, code, patch, or credentials.
4. Observation now deduplicates events and aggregates tasks before calculating project statistics.
5. V2 records strictly validate `project_id + repo_fingerprint`. Hash-chain or HMAC failure prevents conclusions from being formed.
6. `status=PLAN/RUNNING/...` is no longer treated as a failure. Reviewer details are not added again when aggregate counts already include them.
7. Snapshot IDs now include random uniqueness. `source_digest` identifies snapshots from the same source. A Snapshot may only be created once and cannot overwrite an existing name.
8. A Proposal Assessment must match its Snapshot, Signal, Target, Policy, and Evidence. The same evidence fingerprint cannot mechanically regenerate a Proposal.
9. Proposals now support the `IMPLEMENTATION_LINKED / VALIDATION_RECORDED / CLOSED / SUPERSEDED` lifecycle.
10. PreToolUse fails closed for explicit Sol requests, unknown stronger models, and `xhigh/max/ultra`; SubagentStart still records the actual model exposed by the host.
11. The installer now has one transactional implementation. Shell and PowerShell scripts are wrappers only, preventing drift among independent delete/copy implementations.
12. Added the tenth Skill, `controlled-evolution-governance`. Observation governance is separated from ordinary review work to reduce accidental activation.
13. The global AGENTS rules were reduced, while detailed procedures moved into Skills and references to lower persistent context cost.

## Unchanged Safety Boundaries

- `execution_authorization=NONE`
- No automatic modification of Skills, Reviewers, AGENTS rules, model routing, or business code
- No automatic acceptance of Proposals
- No automatic commit, push, deployment, restart, or production write
- Evidence does not grant approval

## Verified

- Python compilation
- JSON and TOML parsing
- 19 local unit and regression tests
- Plugin and standalone installation-structure smoke tests
- Repository/user target-path and symbolic-link protections
- Event V2 non-negative counters, deduplication, cross-project isolation, hash chain, and HMAC
- Regression coverage for misclassifying `status=PLAN`
- Regression coverage for double-counting Reviewer findings
- Immutable Snapshots
- Terra High model-ceiling Hook
- Proposal implementation, validation, and closure state machine
- Schema validation for 35 routing cases

## Explicitly Not Presented as Verified

- Implicit Skill activation, false activation, and missed activation rates in real Codex sessions
- Native Windows PowerShell and Junction adversarial testing
- End-to-end Plugin and Hook loading across Codex host versions
- Long-running, high-concurrency event-write stress testing

These items may be reported as PASS only after they are exercised in the corresponding real environment.
