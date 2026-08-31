# Codex Cross-Project Long-Term Engineering Assistant V6.3 Audit Report

## Scope

The audit covers V6.3 behavioral changes from V6.2: installation transactions, crash recovery, Plugin registration, event chains, lifecycle correlation, self-observation quality, Reviewer attribution, deterministic ZIP files, release evidence, and formal documentation.

The review boundary was logically read-only. No commit, push, deployment, restart, or production operation was performed.

## Reviewer Configuration and Runtime Evidence

- Requested tier: Luna Medium.
- Actual model: TaskOutcomeEvent readback reported `gpt-5.6-luna`.
- Actual reasoning effort: the host event did not provide it, so it remained unverified.
- Reviewers: state/concurrency and test/delivery.
- Maximum automatic model remained within Terra High.

## Preimplementation Findings

The preimplementation review identified these delivery blockers:

1. Release evidence did not bind the formal ZIP, Codex state, and Plugin state.
2. No five-event lifecycle evidence existed from one real session.
3. Self-observation had no computable lifecycle-completeness rate.
4. Reviewer value could be replaced improperly by raw finding count.
5. No byte-identical double-build evidence existed for the ZIP.
6. V6.3 lacked Codex 0.150.1 upgrade acceptance.
7. The new evidence format required a privacy allowlist.

Source and tests incorporated the corresponding implementation. Real-host acceptance ran after the candidate package was complete.

## First Postimplementation Review and Resolution

| Finding | Severity | Resolution |
|---|---|---|
| Crash window between file writes and journal persistence | Blocking | Added per-target `_record_applied` and target-window fault injection |
| Uninstall did not fully record pre-unregistration Plugin state | Blocking | Persisted active Plugin and Marketplace state before unregistration |
| Lifecycle aggregated only by task ID | Blocking | Changed to `(session_id, task_id)` and routed conflicts into the evidence gate |
| Reverse session/task metric was fixed at zero | Medium | Counted missing session bindings while retaining task/session conflict metrics |
| Duplicate event IDs could hide trailing chain damage | Medium | Validate the full chain before deduplication; trailing corruption fails closed |
| Stale-lock logic could seize a live owner | Medium | Check PID liveness and recheck the owner token |
| V6.3 reports were absent | Blocking | Added V6.3 validation and audit reports |
| Validation contained constant PASS values | Blocking | Derived PASS from actual commands and counts |
| Test-count evidence omitted runtime tests | Medium | Ran and reported package and runtime suites separately |

## Second Postimplementation Review and Resolution

Round two confirmed closure of the event, lock, Plugin unregistration-state, and ordinary journal findings, and found a remaining “delete then rebuild” window inside the Plugin Marketplace.

Resolution: build the complete Marketplace in independent staging, calculate target hashes and record mutation intent before replacement, then add crash-recovery tests before and after replacement. The states “old directory untouched,” “target missing,” and “new directory replaced” are now distinguishable deterministically.

## Current Conclusion

All source-level blockers were implemented. Fifty-three package regressions and six runtime regressions passed. Release evidence also tests tampered evidence, illegal evidence paths, correct and incorrect HMAC keys, and cross-parent lifecycle ordering errors.

Formal host acceptance confirmed Codex CLI 0.150.1, Plugin 6.3.0 installed/enabled, ten Skills, seven Reviewers, six Hooks, unchanged main configuration, no loss of historical records, and no active transaction. A real read-only session produced the complete five-event sequence; a Luna Reviewer actually started and stopped; TaskOutcomeEvent 2.0 chain, `project_id`, and `repo_fingerprint` passed validation.

Audit status: formal host portion passed. A release artifact is fully passed only after an external machine proof also verifies byte-identical double builds, artifact hash, Codex and Plugin state, lifecycle report, and validation-report hash for the formal ZIP.
