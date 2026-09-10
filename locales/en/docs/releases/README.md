# Release evidence archive

This archive preserves version-specific build-time records. See [GitHub Releases](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases) for publication and subsequent exact-commit readbacks.

Use the [documentation hub](../README.md) for current operating guidance. Older release pages are historical material and are excluded from default site search.

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/README/)

Release evidence is grouped by semantic version. Each directory contains only the notes, build metadata, audit, and validation material that actually exists for that release; absent evidence is not replaced with empty placeholders.

See [Release automation and artifact provenance](RELEASE_AUTOMATION.md) for version tags, reproducible builds, signed provenance, and maintainer publication gates.

| Version | Release notes | Audit | Validation | Real observation | Build metadata | Package validation |
| --- | --- | --- | --- | --- | --- | --- |
| 7.7.1 | [Notes](v7.7.1/RELEASE_NOTES.md) | [Audit](v7.7.1/AUDIT_REPORT.md) | [Validation](v7.7.1/VALIDATION_REPORT.md) | 329 package + 180 runtime and round-two re-review pass; publication and installed readback remain separate | [JSON](v7.7.1/BUILD_INFO.json) | [JSON](v7.7.1/PACKAGE_VALIDATION.json) |
| 7.7.0 | [Notes](v7.7.0/RELEASE_NOTES.md) | [Audit](v7.7.0/AUDIT_REPORT.md) | [Validation](v7.7.0/VALIDATION_REPORT.md) | Operation v2, 327 package + 179 runtime, and round-two review passed; publication and installed readback remain separate | [JSON](v7.7.0/BUILD_INFO.json) | [JSON](v7.7.0/PACKAGE_VALIDATION.json) |
| 7.6.2 | [Notes](v7.6.2/RELEASE_NOTES.md) | [Audit](v7.6.2/AUDIT_REPORT.md) | [Validation](v7.6.2/VALIDATION_REPORT.md) | Implementation and focused tests only; full validation and post-publication readback pending | [JSON](v7.6.2/BUILD_INFO.json) | [JSON](v7.6.2/PACKAGE_VALIDATION.json) |
| 7.6.1 | [Notes](v7.6.1/RELEASE_NOTES.md) | [Audit](v7.6.1/AUDIT_REPORT.md) | [Validation](v7.6.1/VALIDATION_REPORT.md) | Build-time checks and post-publication readbacks are separate | [JSON](v7.6.1/BUILD_INFO.json) | [JSON](v7.6.1/PACKAGE_VALIDATION.json) |
| 7.6.0 | [Notes](v7.6.0/RELEASE_NOTES.md) | [Audit](v7.6.0/AUDIT_REPORT.md) | [Validation](v7.6.0/VALIDATION_REPORT.md) | Bounded candidate acceptance; exact-version publication checked separately | [JSON](v7.6.0/BUILD_INFO.json) | [JSON](v7.6.0/PACKAGE_VALIDATION.json) |
| 7.5.1 | [Notes](v7.5.1/RELEASE_NOTES.md) | [Audit](v7.5.1/AUDIT_REPORT.md) | [Validation](v7.5.1/VALIDATION_REPORT.md) | Six focused contention/recovery tests passed; see reports for full validation and installation | [JSON](v7.5.1/BUILD_INFO.json) | [JSON](v7.5.1/PACKAGE_VALIDATION.json) |
| 7.5.0 | [Notes](v7.5.0/RELEASE_NOTES.md) | [Audit](v7.5.0/AUDIT_REPORT.md) | [Validation](v7.5.0/VALIDATION_REPORT.md) | Tagged candidate not published; contention timing assumption corrected in 7.5.1 | [JSON](v7.5.0/BUILD_INFO.json) | [JSON](v7.5.0/PACKAGE_VALIDATION.json) |
| 7.4.6 | [Open](v7.4.6/RELEASE_NOTES.md) | [Open](v7.4.6/AUDIT_REPORT.md) | [Open](v7.4.6/VALIDATION_REPORT.md) | Windows 0.153.4 transactional install, Plugin readback, and isolated 0.153.4 cell pass; full matrix/tag/Release require separate readback | [JSON](v7.4.6/BUILD_INFO.json) | [JSON](v7.4.6/PACKAGE_VALIDATION.json) |
| 7.4.5 | [Open](v7.4.5/RELEASE_NOTES.md) | [Open](v7.4.5/AUDIT_REPORT.md) | [Open](v7.4.5/VALIDATION_REPORT.md) | Windows 0.153.3 transactional install, Plugin readback, isolated 0.153.3 cell, and package validation pass; full matrix/tag/Release require separate readback | [JSON](v7.4.5/BUILD_INFO.json) | [JSON](v7.4.5/PACKAGE_VALIDATION.json) |
| 7.4.4 | [Open](v7.4.4/RELEASE_NOTES.md) | [Open](v7.4.4/AUDIT_REPORT.md) | [Open](v7.4.4/VALIDATION_REPORT.md) | Local package-only validation and logical-readonly review passed; remote CI/tag/Release readback pending; historical title backfill complete | [JSON](v7.4.4/BUILD_INFO.json) | [JSON](v7.4.4/PACKAGE_VALIDATION.json) |
| 7.4.3 | [Open](v7.4.3/RELEASE_NOTES.md) | [Open](v7.4.3/AUDIT_REPORT.md) | [Open](v7.4.3/VALIDATION_REPORT.md) | Local package validation, logically read-only independent review, and Windows account reinstall/lifecycle passed; remote CI, tag, and public Release not run | [JSON](v7.4.3/BUILD_INFO.json) | [JSON](v7.4.3/PACKAGE_VALIDATION.json) |
| 7.4.2 | [Open](v7.4.2/RELEASE_NOTES.md) | [Open](v7.4.2/AUDIT_REPORT.md) | [Open](v7.4.2/VALIDATION_REPORT.md) | Windows/Ubuntu eleven-version matrix, package validation, account install, and Codex 0.153.2 native parent/child Agent acceptance pass | [JSON](v7.4.2/BUILD_INFO.json) | [JSON](v7.4.2/PACKAGE_VALIDATION.json) |
| 7.4.1 | [Open](v7.4.1/RELEASE_NOTES.md) | [Open](v7.4.1/AUDIT_REPORT.md) | [Open](v7.4.1/VALIDATION_REPORT.md) | Windows/Ubuntu eleven-version matrix and Codex 0.153.0 native parent/child Agent acceptance passed | [JSON](v7.4.1/BUILD_INFO.json) | [JSON](v7.4.1/PACKAGE_VALIDATION.json) |
| 7.4.0 | [Open](v7.4.0/RELEASE_NOTES.md) | [Open](v7.4.0/AUDIT_REPORT.md) | [Open](v7.4.0/VALIDATION_REPORT.md) | User-level Plugin verified on Codex 0.153.0 | [JSON](v7.4.0/BUILD_INFO.json) | [JSON](v7.4.0/PACKAGE_VALIDATION.json) |
| 7.3.0 | [Open](v7.3.0/RELEASE_NOTES.md) | [Open](v7.3.0/AUDIT_REPORT.md) | [Open](v7.3.0/VALIDATION_REPORT.md) | 3 finalized records, 1 task, `INSUFFICIENT_DATA`; defaults unchanged | [JSON](v7.3.0/BUILD_INFO.json) | [JSON](v7.3.0/PACKAGE_VALIDATION.json) |
| 7.2.0 | [Open](v7.2.0/RELEASE_NOTES.md) | [Open](v7.2.0/AUDIT_REPORT.md) | [Open](v7.2.0/VALIDATION_REPORT.md) | Package `NOT_EVALUATED`; host evidence stored separately | [JSON](v7.2.0/BUILD_INFO.json) | [JSON](v7.2.0/PACKAGE_VALIDATION.json) |
| 7.1.0 | [Open](v7.1.0/RELEASE_NOTES.md) | [Open](v7.1.0/AUDIT_REPORT.md) | [Open](v7.1.0/VALIDATION_REPORT.md) | — | [JSON](v7.1.0/BUILD_INFO.json) | [JSON](v7.1.0/PACKAGE_VALIDATION.json) |
| 7.0.0 | [Open](v7.0.0/RELEASE_NOTES.md) | [Open](v7.0.0/AUDIT_REPORT.md) | [Open](v7.0.0/VALIDATION_REPORT.md) | [Open](v7.0.0/IMPLICIT_TRIGGER_OBSERVATION.md) | [JSON](v7.0.0/BUILD_INFO.json) | [JSON](v7.0.0/PACKAGE_VALIDATION.json) |
| 6.6.1 | [Open](v6.6.1/RELEASE_NOTES.md) | [Open](v6.6.1/AUDIT_REPORT.md) | [Open](v6.6.1/VALIDATION_REPORT.md) | — | [JSON](v6.6.1/BUILD_INFO.json) | [JSON](v6.6.1/PACKAGE_VALIDATION.json) |
| 6.6.0 | [Open](v6.6.0/RELEASE_NOTES.md) | [Open](v6.6.0/AUDIT_REPORT.md) | [Open](v6.6.0/VALIDATION_REPORT.md) | — | [JSON](v6.6.0/BUILD_INFO.json) | [JSON](v6.6.0/PACKAGE_VALIDATION.json) |
| 6.5.0 | [Open](v6.5.0/RELEASE_NOTES.md) | [Open](v6.5.0/AUDIT_REPORT.md) | [Open](v6.5.0/VALIDATION_REPORT.md) | — | [JSON](v6.5.0/BUILD_INFO.json) | — |
| 6.4.0 | [Open](v6.4.0/RELEASE_NOTES.md) | [Open](v6.4.0/AUDIT_REPORT.md) | [Open](v6.4.0/VALIDATION_REPORT.md) | — | [JSON](v6.4.0/BUILD_INFO.json) | — |
| 6.3.0 | [Open](v6.3.0/RELEASE_NOTES.md) | [Open](v6.3.0/AUDIT_REPORT.md) | [Open](v6.3.0/VALIDATION_REPORT.md) | — | [JSON](v6.3.0/BUILD_INFO.json) | — |
| 6.2.0 | [Open](v6.2.0/RELEASE_NOTES.md) | [Open](v6.2.0/AUDIT_REPORT.md) | [Open](v6.2.0/VALIDATION_REPORT.md) | — | [JSON](v6.2.0/BUILD_INFO.json) | — |
| 6.1.0 | [Open](v6.1.0/RELEASE_NOTES.md) | [Open](v6.1.0/AUDIT_REPORT.md) | [Open](v6.1.0/VALIDATION_REPORT.md) | — | [JSON](v6.1.0/BUILD_INFO.json) | — |
| 6.0.0 | [Open](v6.0.0/RELEASE_NOTES.md) | — | — | — | [JSON](v6.0.0/BUILD_INFO.json) | — |

These files describe the state of their original release. The current host state still needs independent installer verification and `codex plugin list --json` readback.
