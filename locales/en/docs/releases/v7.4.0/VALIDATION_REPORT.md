# V7.4.0 Validation Report

Status: local package validation, real user-level installation, and post-implementation review passed.

- Full validation on Python 3.13.15 passed 198 package tests and 6 runtime tests.
- Semantic lint, 45 routing cases, model ceiling, payload integrity, and worktree side-effect gates passed.
- Both locale ZIPs were built twice with identical digests and passed archive verification.
- The user-level Plugin was force-upgraded from V7.3.0 to V7.4.0 on Codex CLI 0.153.0. Installer verify/status/doctor and independent Plugin readback passed.
- Source, Marketplace, and Plugin cache each contained 182 managed files with the same payload digest.
- Separate upgrade regressions cover V7.2.0 and V7.3.0 Marketplace snapshots missing `interface.displayName`.

Python 3.11 and the cross-platform matrix are post-tag CI evidence because Python 3.11 is not installed on this host. Public Release, remote tag, and CI status require separate post-publication readback.

V7.4.0 verifies Codex CLI 0.153.0 only. The current-plus-ten stable compatibility window is deferred to V7.4.1.
