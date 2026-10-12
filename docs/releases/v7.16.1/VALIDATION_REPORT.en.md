<!-- Generated from locales/en/docs/releases/v7.16.1/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.16.1 Validation Report

This report accompanies the source candidate. Local tests do not assert publication or field effectiveness.

- Before repair, three real-entrypoint assertions failed consistently: parent PreToolUse/PostToolUse at 2 MiB + 1 byte and an 8 MiB image-shaped result.
- After repair, 52 focused new/adversarial and existing V5/G6 regression tests passed, covering late identities, nested spoofing, escaped duplicate keys, malformed JSON/UTF-8 and resource limits.
- Local Python 3.14 synthetic measurements: 8/32 MiB image-shaped inputs took approximately 0.015/0.057 seconds with about 2.2 MiB peak parser allocation, excluding caller-side input construction. This is not a cross-machine performance guarantee.

`RELEASE_COMPLETE` requires exact-commit CI, bilingual packages, checksums, provenance and public Release readback. `INCIDENT_EFFECTIVE` additionally requires installed loading and a real Desktop large-result event. Synthetic tests do not establish installation, restart or field acceptance. Child protections and fail-closed resource limits remain.
