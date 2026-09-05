# V7.4.6 Release Notes

Version: 7.4.6
Theme: Codex CLI 0.153.4 stable compatibility
Host window: Codex CLI 0.153.4 plus the ten preceding stable releases

## Upstream changes

- OpenAI Codex CLI 0.153.4 fixes GPT-6-Astra visibility in the bundled model picker and makes it the bundled default when no model is selected explicitly.
- Async-question guidance now applies only when the host exposes the corresponding question tool.
- These changes do not alter the frozen Plugin, Marketplace, or Hook contracts, so this release advances the compatibility window without a protocol redesign.

## Package changes

- Advances the closed compatibility registry to 0.153.4 and freezes `0.153.4`, `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, `0.151.0`, `0.150.1`, `0.150.0`, and `0.149.1`.
- Pins the official npm tarball, SRI, SHA-256, CLI-help, and Plugin-JSON evidence. Version 0.149.0 leaves the active window but remains in historical reports.
- Updates the Windows/Ubuntu compatibility matrix, installer, release validation, bilingual documentation, and site indexes to V7.4.6.
- Automatic subagent profiles remain limited to Luna/Terra. The upstream GPT-6-Astra default change does not expand automatic routing policy.

## Local evidence boundary

- The native Windows CLI was updated through the same global npm channel from 0.153.3 to 0.153.4; version, help, login status, and Plugin-list readback pass.
- Official-artifact verification, isolated CLI, Plugin add/list/remove round-trip, and synthetic Hook checks pass for 0.153.4.
- V7.4.6 account-level transactional installation, `verify`, `status`, `doctor`, Plugin activation, and source/Marketplace/cache identity for all 182 payload files pass; a recoverable backup is retained.
- Actual uninstall/rollback and a real parent/child Agent lifecycle journey were not exercised. The complete eleven-version matrix, remote CI, tag, six-asset provenance, and public Release require separate readback.
