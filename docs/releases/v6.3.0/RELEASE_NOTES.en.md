# Codex Cross-Project Long-Term Engineering Assistant V6.3 Release Notes

## Release Scope

V6.3 strengthens installation transactions, release evidence, and observation quality on the native Windows Codex CLI 0.150.1 compatibility baseline established by V6.2. Compatibility is retained for the 10 Skills, 7 Reviewers, 6 Hooks, TaskOutcomeEvent 2.0, dual project isolation, and the Terra High automatic ceiling.

## Major Changes

### Durable Installation Transactions

- Create a transaction journal and mutual-exclusion lock before the first managed write.
- Record backups, filesystem actions, Plugin registration actions, and commit state.
- Add `status` and `recover` for deterministic recovery after process interruption.
- During recovery, validate ownership drift, link-like paths, and backup integrity.
- Archive a successfully committed transaction without leaving an active journal behind.

### Reproducible Releases and Machine-Readable Evidence

- Fix ZIP entry order, timestamps, file modes, and compression parameters.
- Require two independent builds to be byte-for-byte identical.
- Bind release evidence to the official ZIP SHA-256, Codex 0.150.1, Plugin 6.3.0 state, and hashes of validation evidence.
- Support evidence-tamper detection and optional HMAC integrity authentication.

### Real Lifecycle Acceptance

- Accept `TURN_OPENED`, `SUBAGENT_STARTED`, `SUBAGENT_STOPPED`, `TASK_COMPLETED`, and `SESSION_ENDED` from one real Codex session.
- Validate event order, task correlation, project identity, repository fingerprint, and the complete hash chain.
- External reports retain only hashed session and task references.

### Observation Quality and Reviewer Attribution

- Add task/session lifecycle-completion and SessionEnd-coverage rates.
- Detect missing, duplicate, and out-of-order events, including cross-task and cross-session contamination.
- Add coverage metrics for actual model, explicit terminal outcome, project binding, and repository binding.
- Base Reviewer value on finding attribution, adoption, repair, recurrence, regression prevention, duration, and cost indicators.
- Report `insufficient-evidence` when sample size or causal evidence is inadequate; finding count alone is not treated as value.

## Compatibility and Safety Boundaries

- Supports upgrades from V6.1.0 and V6.2.0.
- Retains the previous state schema and historical project context.
- `execution_authorization=NONE`.
- Evolution Proposals are neither accepted nor implemented automatically.
- Skills, Reviewers, the main Agent model, and business repositories are not modified automatically.
- No automatic commit, push, deployment, restart, or production operation.
- The automatic-subagent route remains Luna Low → Luna Medium → Terra Medium → Terra High, with Terra High as the ceiling.

## Acceptance Status

Source tests, independent review, official ZIP hashes, real Plugin upgrade, and lifecycle evidence are governed by `VALIDATION_REPORT_V6.3.md`, `V6.3_AUDIT_REPORT.md`, and machine evidence stored outside the package. A planned state must not be reported as complete before the corresponding evidence exists.
