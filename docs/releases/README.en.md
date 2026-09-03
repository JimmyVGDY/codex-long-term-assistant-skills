# Release evidence archive

V7.4.1 is the current release. Every other version in this table is retained only for release traceability. Its detail pages display a historical-material warning and are excluded from default site search; they are not current installation or operating guidance.

Chinese: [README.md](README.md)

Release evidence is grouped by semantic version. Each directory contains only the notes, build metadata, audit, and validation material that actually exists for that release; absent evidence is not replaced with empty placeholders.

See [Release automation and artifact provenance](RELEASE_AUTOMATION.en.md) for version tags, reproducible builds, signed provenance, and maintainer publication gates.

| Version | Release notes | Audit | Validation | Real observation | Build metadata | Package validation |
| --- | --- | --- | --- | --- | --- | --- |
| 7.4.1 | [Open](v7.4.1/RELEASE_NOTES.en.md) | [Open](v7.4.1/AUDIT_REPORT.en.md) | [Open](v7.4.1/VALIDATION_REPORT.en.md) | Windows/Ubuntu eleven-version matrix and Codex 0.153.0 native parent/child Agent acceptance passed | [JSON](v7.4.1/BUILD_INFO.json) | [JSON](v7.4.1/PACKAGE_VALIDATION.json) |
| 7.4.0 | [Open](v7.4.0/RELEASE_NOTES.en.md) | [Open](v7.4.0/AUDIT_REPORT.en.md) | [Open](v7.4.0/VALIDATION_REPORT.en.md) | User-level Plugin verified on Codex 0.153.0 | [JSON](v7.4.0/BUILD_INFO.json) | [JSON](v7.4.0/PACKAGE_VALIDATION.json) |
| 7.3.0 | [Open](v7.3.0/RELEASE_NOTES.en.md) | [Open](v7.3.0/AUDIT_REPORT.en.md) | [Open](v7.3.0/VALIDATION_REPORT.en.md) | 3 finalized records, 1 task, `INSUFFICIENT_DATA`; defaults unchanged | [JSON](v7.3.0/BUILD_INFO.json) | [JSON](v7.3.0/PACKAGE_VALIDATION.json) |
| 7.2.0 | [Open](v7.2.0/RELEASE_NOTES.en.md) | [Open](v7.2.0/AUDIT_REPORT.en.md) | [Open](v7.2.0/VALIDATION_REPORT.en.md) | Package `NOT_EVALUATED`; host evidence stored separately | [JSON](v7.2.0/BUILD_INFO.json) | [JSON](v7.2.0/PACKAGE_VALIDATION.json) |
| 7.1.0 | [Open](v7.1.0/RELEASE_NOTES.en.md) | [Open](v7.1.0/AUDIT_REPORT.en.md) | [Open](v7.1.0/VALIDATION_REPORT.en.md) | — | [JSON](v7.1.0/BUILD_INFO.json) | [JSON](v7.1.0/PACKAGE_VALIDATION.json) |
| 7.0.0 | [Open](v7.0.0/RELEASE_NOTES.en.md) | [Open](v7.0.0/AUDIT_REPORT.en.md) | [Open](v7.0.0/VALIDATION_REPORT.en.md) | [Open](v7.0.0/IMPLICIT_TRIGGER_OBSERVATION.en.md) | [JSON](v7.0.0/BUILD_INFO.json) | [JSON](v7.0.0/PACKAGE_VALIDATION.json) |
| 6.6.1 | [Open](v6.6.1/RELEASE_NOTES.en.md) | [Open](v6.6.1/AUDIT_REPORT.en.md) | [Open](v6.6.1/VALIDATION_REPORT.en.md) | — | [JSON](v6.6.1/BUILD_INFO.json) | [JSON](v6.6.1/PACKAGE_VALIDATION.json) |
| 6.6.0 | [Open](v6.6.0/RELEASE_NOTES.en.md) | [Open](v6.6.0/AUDIT_REPORT.en.md) | [Open](v6.6.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.6.0/BUILD_INFO.json) | [JSON](v6.6.0/PACKAGE_VALIDATION.json) |
| 6.5.0 | [Open](v6.5.0/RELEASE_NOTES.en.md) | [Open](v6.5.0/AUDIT_REPORT.en.md) | [Open](v6.5.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.5.0/BUILD_INFO.json) | — |
| 6.4.0 | [Open](v6.4.0/RELEASE_NOTES.en.md) | [Open](v6.4.0/AUDIT_REPORT.en.md) | [Open](v6.4.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.4.0/BUILD_INFO.json) | — |
| 6.3.0 | [Open](v6.3.0/RELEASE_NOTES.en.md) | [Open](v6.3.0/AUDIT_REPORT.en.md) | [Open](v6.3.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.3.0/BUILD_INFO.json) | — |
| 6.2.0 | [Open](v6.2.0/RELEASE_NOTES.en.md) | [Open](v6.2.0/AUDIT_REPORT.en.md) | [Open](v6.2.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.2.0/BUILD_INFO.json) | — |
| 6.1.0 | [Open](v6.1.0/RELEASE_NOTES.en.md) | [Open](v6.1.0/AUDIT_REPORT.en.md) | [Open](v6.1.0/VALIDATION_REPORT.en.md) | — | [JSON](v6.1.0/BUILD_INFO.json) | — |
| 6.0.0 | [Open](v6.0.0/RELEASE_NOTES.en.md) | — | — | — | [JSON](v6.0.0/BUILD_INFO.json) | — |

These files describe the state of their original release. The current host state still needs independent installer verification and `codex plugin list --json` readback.
