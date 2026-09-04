# V7.4.5 Release Notes

Version: 7.4.5
Theme: Codex CLI 0.153.3 stable compatibility
Host window: Codex CLI 0.153.3 plus the ten preceding stable releases

## Upstream changes

- OpenAI Codex CLI 0.153.3 adds GPT-6-Astra Mantle/Runtime global and US routes to the Amazon Bedrock model picker.
- Astra async-question guidance is corrected.
- These changes do not alter the frozen Plugin, Marketplace, or Hook contracts, so this release advances the compatibility window without a protocol redesign.

## Package changes

- Advances the closed compatibility registry to 0.153.3 and freezes `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, `0.151.0`, `0.150.1`, `0.150.0`, `0.149.1`, and `0.149.0`.
- Pins the official npm tarball, SRI, SHA-256, CLI-help, and Plugin-JSON evidence. Version 0.148.0 leaves the active window but remains in historical reports.
- Updates the Windows/Ubuntu compatibility matrix, installer, release validation, bilingual documentation, and site indexes to V7.4.5.
- Automatic subagent profiles remain limited to Luna/Terra. The upstream GPT-6-Astra picker change does not expand automatic routing policy.

## Local evidence boundary

- The native Windows CLI was updated through the same global npm channel from 0.153.2 to 0.153.3; `--help`, login status, and Plugin-list readback pass.
- Official-artifact verification, isolated CLI, Plugin add/list/remove round-trip, and synthetic Hook checks pass for 0.153.3.
- V7.4.5 account-level transactional installation, `verify`, `status`, `doctor`, Plugin activation, and source/Marketplace/cache payload identity pass.
- Actual uninstall/rollback and a real parent/child Agent lifecycle journey were not exercised. Remote CI, tag, asset provenance, and public Release require separate readback.
