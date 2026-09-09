# V7.4.3 Release Notes

Version: 7.4.3
Host window: Codex CLI 0.153.2 and the ten preceding stable releases

## Core correction

- Host runtime model identity and reasoning effort are no longer Agent inputs, evidence, or governance conditions. Runtime code does not read, infer, store, attest, bill, score, or gate on them.
- Automatic dispatch uses only four abstract approved profiles: `luna-low`, `luna-medium`, `terra-medium`, and `terra-high`. Exact model requests may be validated transiently by the PreToolUse host adapter; persistent state keeps only the approved profile, permit reference, and reserved units.
- TaskOutcomeEvent advances to V3, DelegationBudget to V2, and Reviewer results to V4. All three remove host runtime model identity from their contracts.
- Calibration and Evolution compare outcome value per reserved unit between approved profiles and no longer emit host-model-identity escalation signals.

## Compatibility and migration

- Event V2 and Budget V1 chains from V7.4.2 and earlier are still verified against their original hash/HMAC contracts before an allowlisted projection is exposed read-only.
- Legacy and current event and budget chains remain physically separate. The current runtime refuses to append to a legacy chain or mix schemas.
- Historical model-identity fields do not reach V3 aggregation, snapshots, assessments, proposals, Reviewer state, or release reports.
- Reviewer state migration persists only a safe projection and does not reserialize legacy runtime model information.

## Release gates

- Adds a privacy-boundary lint, dispatch-policy acceptance, Lifecycle Acceptance V2, and Release Attestation V2.
- Release reports attest only the approved-profile gate, budget reservation, lifecycle correlation, chain integrity, and privacy scan. They do not attest which model a host ran.
- V7.4.3 retains the V7.4.2 frozen Codex CLI 0.153.2 compatibility window and does not admit future or prerelease hosts.

## Current status

Windows account-level transactional reinstall, Plugin enablement/version/payload readback, and installed-Hook lifecycle sealing passed. This file does not pre-claim remote CI, tag creation, or public Release publication; final status comes from post-publication readback.
