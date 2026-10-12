# V7.16.1 Validation Report

The stable release was [published](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.16.1) at **2026-10-12 16:26:46 UTC (2026-10-13 00:26:46 Asia/Shanghai)**, bound to commit `8a355abbbd68af32145364d1b5a7c65985f0baf1`. Later documentation updates do not replace the tag or signed artifacts.

## CI and public artifacts

All four complete configurations passed in the [release workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38269549971). Counts below come from its structured reports.

| Platform | Python | Package tests | Runtime tests |
|---|---|---|---|
| Ubuntu | 3.11 | 1,150 passed, 42 conditional skips | 233 passed, 6 conditional skips |
| Ubuntu | 3.13 | 1,150 passed, 42 conditional skips | 233 passed, 6 conditional skips |
| Windows | 3.11 | 1,190 passed, 2 conditional skips | 239 passed |
| Windows | 3.13 | 1,191 passed, 1 conditional skip | 239 passed |

[PR CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38260958780) and [main CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38269253642) passed. Reproducible bilingual packages, checksums, witnesses and GitHub attestation verification passed. Provenance binds this repository, the commit above, `refs/tags/v7.16.1` and the release workflow. All six public assets were anonymously downloaded and matched the signed candidate's sizes and SHA-256 digests.

## Local installation and runtime checks

- Before repair, three real-entrypoint assertions failed: parent PreToolUse/PostToolUse at 2 MiB + 1 byte and an 8 MiB image-shaped result.
- After repair, 52 focused new/adversarial and existing V5/G6 tests passed; 25 affected release/integrity tests passed.
- Local Python 3.14 synthetic 8/32 MiB inputs took about 0.015/0.057 seconds with about 2.2 MiB peak parser allocation, excluding input construction. This is not a cross-machine guarantee.
- Managed upgrade from the official Chinese package passed installation verification and strict doctor. Version 7.16.1 is enabled and host-compatible; source, marketplace and cache agree on all 330 payload files.
- Fresh installed-Hook processes return neutral for oversized parent PreToolUse/PostToolUse events while preserving the 2 MiB child rejection. A real `view_image` call returned an image result containing 4,196,117 characters.
- Desktop was not restarted. The original project's complete business workflow was not replayed.

## Retained limits

An additional local Windows/Python 3.14 full run had seven PowerShell-related failures/errors. Targeted diagnosis confirmed Restricted policy blocked scripts; all seven passed with RemoteSigned limited to the test process, leaving system policy unchanged. A later full run retained one dangling-reparse test ERROR; that case passed standalone and with forced junction fallback. Its full-run cause remains unproven. Original failures are retained; assertions were not removed and cases were not skipped.

`RELEASE_COMPLETE` is supported by exact-commit CI, signed artifacts and public readback. `INCIDENT_EFFECTIVE` has evidence only for the installed Hook and native large-result call; original-project business acceptance remains outstanding. See the [audit report](AUDIT_REPORT.md) for review scope and limits.
