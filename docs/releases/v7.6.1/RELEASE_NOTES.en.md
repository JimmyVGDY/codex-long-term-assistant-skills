<!-- Generated from locales/en/docs/releases/v7.6.1/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.6.1 Release Notes

This patch corrects documentation maintenance and release-source boundaries.

- Distinguish the six-event observation chain from seven Hook registrations; correct migration versions, budget ownership and format descriptions.
- Maintain English content in locales/en and generate sibling projections from one catalog, with fact and drift checks.
- Provide stable usage, configuration/recovery and architecture paths while preserving old paths and section anchors.
- Build from Git-tracked source or explicit Gitless snapshots with content hashes; both locales use captured inputs.
- Archive historical tasks, caches and old outputs using verified manifests while preserving current Profile, index and optional gate bindings.

Existing installation/recovery supports upgrades from V7.6.0. Default-disabled reuse gates, data formats and the frozen compatibility window remain unchanged.

[Validation record](VALIDATION_REPORT.en.md) · [Maintenance guide](../../DOCUMENTATION_MAINTENANCE.en.md)
