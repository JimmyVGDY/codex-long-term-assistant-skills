# Codex Cross-Project Long-Term Engineering Assistant V6.4 Release Notes

## Release Scope

V6.4 targets native Windows Codex CLI 0.150.1 and focuses on Plugin payload identity, installation recovery, segmented events, and unified release verification. It remains compatible with V6.3's 10 Skills, 7 Reviewers, 6 Hooks, TaskOutcomeEvent 2.0, dual project isolation, and Terra High automatic ceiling.

## Major Changes

### Identity Chain from ZIP to Runtime Cache

- Added `PLUGIN_PAYLOAD_MANIFEST.json`, covering only the four runtime payload roots: `.codex-plugin`, `skills`, `hooks`, and `runtime`.
- Canonically sort entry paths, file sizes, and SHA-256 values.
- Calculate one projected digest for the ZIP, Marketplace source, and Plugin cache.
- Fail closed on unknown payloads, path escapes, symbolic links, Junctions, and reparse points.
- `verify-release.py` combines artifact, host, Plugin, lifecycle, and payload evidence into one conclusion.

### Recoverable V6.3-to-V6.4 Upgrade

- Explicitly migrate installation state from schema 1 to schema 2 while retaining unknown fields, previous backup references, and historical state.
- Update only this package's payload subtree in the Marketplace and merge only this package's manifest entry; unknown assets are not replaced.
- Record candidate Plugin-cache paths, old/new digests, backups, activation readback, and recovery actions in the transaction journal.
- Exercise recovery at hard-crash boundaries around Plugin add, cache verification, and state writes.
- Recursively reject every link-like descendant of a managed tree before digesting, backing up, copying, or deleting it.

### Secure Event Segmentation and Host Facts

- TaskOutcomeEvent V2 writes can continue across segments.
- Readers, lifecycle acceptance, and observation use the same cross-segment verification entry point.
- A partial record in the active file is quarantined for audit while the intact event chain remains usable.
- A lock owned by a dead process can be recovered; a live owner cannot be preempted based only on elapsed time.
- Explicitly invalid terminal outcomes, unknown actual models, and hash-consistent but schema-invalid legacy records all fail closed.
- `actual_model`, `actual_reasoning_effort`, and `terminal_outcome` accept only explicit host fields and are never inferred from generic aliases.
- The lifecycle validator evaluates actual Hook fields separately from Codex subtask-session evidence. When the host does not expose the model to Hooks, Hook evidence remains `unavailable`; Reviewer lifecycle can still be accepted through correlated parent session, subtask turn, model, and reasoning-effort observations.

### Codex Capability Detection

- `doctor` confirms Codex 0.150.1 before any write.
- It checks the actual command capabilities for `plugin list --json`, Marketplace add/remove, and Plugin add/remove.
- Installation stops and retains diagnostic information when the version is unknown, a capability is missing, or exact Plugin-version readback fails.

## Compatibility and Safety Boundaries

- Supports upgrades from 6.1.0, 6.2.0, and 6.3.0.
- Retains historical project context, Events, Snapshots, Assessments, Proposals, and upgrade backups.
- `execution_authorization=NONE`.
- Does not rewrite the main Agent model configuration.
- Reviewer TOML files do not hard-code models.
- The automatic route remains Luna Low → Luna Medium → Terra Medium → Terra High.
- Proposals are neither accepted nor implemented automatically.
- No automatic commit, push, deployment, restart, or production operation.

## Acceptance Notes

In-package regression results, independent review, and candidate implementation evidence are recorded in `VALIDATION_REPORT_V6.4.md` and `V6.4_AUDIT_REPORT.md`. The official ZIP, real account-level Plugin state, and lifecycle evidence form a complete release conclusion only after both the unified verifier and the external attestation pass.
