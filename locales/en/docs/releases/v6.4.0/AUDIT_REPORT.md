# Codex Cross-Project Long-Term Engineering Assistant V6.4 Audit Report

## Scope

The audit covers V6.4 changes from V6.3: Marketplace ownership, Plugin-cache transactions, state-schema migration, payload identity, event segmentation, partial-record recovery, host fact sources, capability detection, unified validation, and delivery documentation.

The review boundary was logically read-only. No commit, push, deployment, restart, or production operation was performed.

## Preimplementation Review

Six blocking root-cause groups were identified:

1. Marketplace updates must not replace the entire tree and destroy unknown assets.
2. Plugin cache must participate in journaling, backup, recovery, and exact readback.
3. State schema 1 -> 2 requires explicit migration while preserving unknown fields.
4. Lifecycle, self-observation, and CLI must share one segmented-reader entry point.
5. Cross-segment reads and rotation need one consistent topology snapshot.
6. Partial active tails and host-fact sources need fail-closed protocols.

The design and test matrix incorporated these revisions.

## First Postimplementation Review

| Finding | Severity | Resolution |
|---|---|---|
| Invalid terminal outcomes silently became UNKNOWN | Blocking | Only missing fields may become UNKNOWN; explicit invalid values raise a contract error |
| Existing events validated hashes but not schema | Blocking | Unified reader now validates fields, schema, and canonical form strictly |
| `actual_model` allowlist was too broad | Blocking | Replaced with an exact set of known Codex models |
| Nested Junction/Reparse descendants were not rejected recursively | Medium | Unified recursive checks before hashing, backup, copy, or deletion |

## Second Postimplementation Review

Round two used a new packet and source hash to rereview the four repairs. Security and test-delivery Reviewers confirmed closure with no residual findings, reusing 65 package regressions, six runtime regressions, and targeted security evidence. The Marketplace policy, category, and interface were then aligned with current Codex Plugin requirements and isolated real-CLI and upgrade-compatibility tests were added. A real lifecycle test exposed acceptance-contract handling when Hook model fields are missing. After correction and a correlated-host-session evidence test, package regressions reached 67.

## Current Conclusion

Source-level and candidate-package blockers are closed. Sixty-seven package regressions, six runtime regressions, and semantic gates passed. The formal ZIP, real-account upgrade, new-session lifecycle, three-way payload digest, and external unified attestation had not yet run, so the result was: candidate implementation passed; formal release unverified.

Formal release may become passed only when later host readback simultaneously confirms Codex 0.150.1, Plugin 6.4.0 installed/enabled, ten Skills, seven Reviewers, six Hooks, event-chain continuity, dual project isolation, and matching payload identity.
