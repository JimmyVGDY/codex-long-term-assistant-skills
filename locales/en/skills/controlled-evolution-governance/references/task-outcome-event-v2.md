# TaskOutcomeEvent V2

V6 events retain lifecycle metadata only. Core keys include `event_id/event_type/session_id/turn_id/task_id/project_id/repo_fingerprint/terminal_outcome/actual_model/actual_reasoning_effort`, three fact-source fields, and non-negative counters.

- `event_id` must be unique.
- Both `project_id` and `repo_fingerprint` must match the current project.
- `terminal_outcome` accepts only `PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN`.
- Use `UNKNOWN` when no explicit terminal outcome is available. A Stop event must not be treated automatically as success.
- `actual_model_source/actual_reasoning_effort_source/terminal_outcome_source` accept only controlled source values. For model fields, only `host-attested-hook-payload` qualifies as V6.6 runtime `VERIFIED` evidence. The legacy `hook-payload` value remains for historical compatibility. Generic model, reasoning, status, or configuration values must not be inferred as actual host facts.
- Raw prompts, responses, source code, diffs, authentication credentials, and other content are excluded by default.
- JSONL records use a forward SHA-256 chain. When the active file reaches its threshold, continuous read-only segments are created under the same lock while preserving chain continuity across segments. Any uncommitted active-file tail is moved into a summarized quarantine file. Corruption in a historical segment fails closed.
- When `CP_ASSISTANT_HMAC_KEY` is configured, HMAC integrity verification is added. This detects tampering; it does not provide non-repudiation.

## V6.5 Integrity Seals

- The original TaskOutcomeEvent schema remains at 2.0.
- Keyring-based HMAC values are written as detached seals and do not alter the event envelope.
- `SEALED_CURRENT` means that the current chain head is sealed. A valid new event creates an unsealed tail.
- V6.4 event writes and V6.5 seals can coexist. A historical seal remains valid when a new tail is appended.
- Windows DPAPI and POSIX keyrings are isolated by issuer and are never used silently across backends.

## Reviewer Calibration Input

`reviewer_results` are deduplicated by `(task_id, reviewer, result_id)`. Replays with the same identity count once. Conflicting payloads enter `CONFLICT`, and records without a stable identity are excluded from calibration samples. Calibration state may produce an observation or a Proposal candidate, but it never grants execution authority.

## V6.6 Delayed Sealing and Model Evidence

- SessionEnd does not scan or seal the event chain within its three-second budget. It creates only a minimal HMAC-protected job and launches a detached worker.
- The worker idempotently appends `SESSION_ENDED`, verifies the complete chain, creates a seal, and commits completion evidence.
- The job, event, and seal are all bound to `project_id + repo_fingerprint`; cross-project copying fails closed.
- `requested_model_policy`, `runtime_model_evidence`, and `diagnostic_model_observation` independently record the requested ceiling, trustworthy host attestation, and diagnostic observation.
- Without an external host trust anchor, `runtime_model_evidence` must remain `UNAVAILABLE`.
- Closed segments may be copied non-destructively into the archive and verified by an immutable manifest hash chain. Archiving never deletes canonical Events, Snapshots, or Proposals.
