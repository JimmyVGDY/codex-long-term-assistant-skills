# V6.5 Release Notes

Version: 6.5.0
Target host: Native Windows Codex CLI 0.150.1

## Major Changes

1. Added the `host_facts` adapter. Host session JSONL is read through stable snapshots with size limits, reparse-point rejection, parent-session/subtask correlation, and conflict detection. Only summaries are emitted. This source is permanently classified as `DIAGNOSTIC` and cannot independently prove model-gate or release status.
2. Added Integrity Keyring V1. Windows protects keys with the current account's DPAPI; POSIX uses files with mode 0600. The `event-hmac` and `release-attestation` purposes are isolated, and rotation retains historical verification keys.
3. Added detached event seals. A seal is independent of the original TaskOutcomeEvent 2.0 record and binds the chain head, record count, preceding seal, issuer, and key ID. When a V6.4 process continues writing, it creates a valid unsealed tail without invalidating historical seals.
4. Added Reviewer Calibration V1. Results are deduplicated by stable `result_id`, conflicting records are detected, and the report includes independent task count, attribution coverage, Wilson 95% intervals, cost/benefit indicators, and calibration state.
5. Release attestations now support keyring HMAC rotation and reject host-only model evidence, an unsealed current event-chain head, and keyring-to-legacy downgrade. Real lifecycle acceptance and the installed PreToolUse model gate are evaluated separately, so diagnostic session records from Codex 0.150.1 cannot be presented as trusted Hook model evidence.

## Unchanged

- 10 Skills, 7 Reviewers, and 6 Hooks;
- TaskOutcomeEvent schema 2.0;
- Plugin ID and Marketplace ID;
- the automatic-subagent route and Terra High ceiling;
- no hard-coded model in Reviewer TOML and no override of the main Agent model;
- `execution_authorization=NONE`;
- no automatic capability changes, Proposal acceptance, commit, push, deployment, restart, or production operation;
- retention of V6.4 project context, events, Snapshots, Proposals, and upgrade backups.

## Upgrade

V6.4.0 can be upgraded directly in Plugin mode. The formal installation path remains `doctor -> dry-run -> install -> verify -> codex plugin list --json`.
