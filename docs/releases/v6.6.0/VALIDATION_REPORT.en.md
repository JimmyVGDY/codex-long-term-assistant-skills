# V6.6 In-Package Validation Report

Version: 6.6.0

Status: package-level validation passed; real installation and lifecycle evidence are recorded in the external upgrade report

## Scope

- Python syntax, JSON, TOML, and semantic gates.
- Ten Skills, seven Reviewers, six Hooks, and SessionEnd timeout=3.
- Multiprocess event writes with Windows spawn and keyring rotation.
- OS lock release after forced termination.
- Keyring temporary-file fsync and breakpoints before/after replace.
- Signed SessionEnd enqueue; worker claim/append/seal/ack recovery; event-ID idempotency.
- Reviewer Calibration V2.
- Non-destructive archive, capacity budgets, dual project binding, and privacy-projected health overview.
- Plugin installation transaction, rollback, payload identity, and deterministic ZIP.

## Executed Results

- Package tests: 92/92 PASS.
- Runtime tests: 6/6 PASS.
- V6.6 deepening tests: 17/17 PASS.
- Payload: 170 files, digest `2251421c9350e29022662a784cf1ef7bb98f4f36de4b0775a751c6f1b0e92885`.
- Semantic lint: PASS.
- Preimplementation Reviewers: 2; postimplementation Reviewers: 2; targeted rereview: 2; every blocking root cause closed.
- Runtime tests cover six Hooks on Windows paths containing spaces, Junction/reparse, PID reuse, old-or-new seal publication, and SessionEnd failure diagnostics.

## Model-Evidence Semantics

- `requested_model_policy`: proven by positive and negative PreToolUse cases.
- `runtime_model_evidence`: VERIFIED only when trustworthy host attestation passes.
- `diagnostic_model_observation`: diagnostic evidence only and never used for VERIFIED.

For Codex 0.150.1, the expected actual fields are `PASS / UNAVAILABLE / <diagnostic observation>`.

## Security Boundaries

- Events, archives, queues, and health overviews do not retain prompts, complete responses, source bodies, diffs, or credentials.
- Archiving copies only closed segments, never moves the canonical chain, and never deletes history automatically.
- Project aggregation continues to validate both `project_id + repo_fingerprint`.
- Proposals retain `execution_authorization=NONE`.
