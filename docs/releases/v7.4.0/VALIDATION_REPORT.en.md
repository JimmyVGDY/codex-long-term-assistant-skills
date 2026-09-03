# V7.4.0 Validation Report

Status: local package validation, real user-level installation, and post-implementation review passed.

- Full validation on Python 3.13.15 passed 198 package tests and 6 runtime tests.
- Semantic lint, 45 routing cases, model ceiling, payload integrity, and worktree side-effect gates passed.
- Both locale ZIPs were built twice with identical digests and passed archive structure and normalized-timestamp verification.
- The user-level Plugin was force-upgraded from V7.3.0 to V7.4.0 on Codex CLI 0.153.0; installer verify, status, and doctor passed.
- Independent `codex plugin list --json` readback reported `installed=true`, `enabled=true`, and `version=7.4.0`.
- Source, Marketplace, and Plugin cache each contained 182 managed files with the same payload digest.
- Separate upgrade regressions cover V7.2.0 and V7.3.0 Marketplace snapshots missing `interface.displayName`.

Python 3.11 is not installed on this host. The Python 3.11 and cross-platform matrix is verified by post-tag GitHub Actions and remains external release evidence. Public Release, remote tag, and CI status must likewise be read back after publication and are not pre-claimed here.

V7.4.0 verifies Codex CLI 0.153.0 only. The current-plus-ten stable compatibility window is explicitly deferred to V7.4.1.
