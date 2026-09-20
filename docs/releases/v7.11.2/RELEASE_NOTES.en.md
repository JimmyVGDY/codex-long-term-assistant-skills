<!-- Generated from locales/en/docs/releases/v7.11.2/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.11.2 Release Notes

V7.11.2 is a stable Codex CLI compatibility patch targeting official stable 0.155.1. The only upstream behavior change disables reasoning summaries by default in the local TUI so providers that do not support the field do not reject requests; explicit settings remain honored.

## Changes

- Freeze the window at `0.155.1`, `0.155.0`, `0.154.0`, `0.153.4`, `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, and `0.151.0`.
- Register official npm integrity, tarball SHA-256, the `rust-v0.155.1` tag commit, and Hook/apply_patch source digests.
- Preserve Plugin, Marketplace, Operation v2, ten Reviewer profiles, budget, and legacy replay behavior. Future, prerelease, and out-of-window hosts remain fail-closed.
- Support upgrades from V7.11.1 and the versions already declared by the manifest.

Git commit, tag, GitHub Release, account installation, and effectiveness remain separate facts and require separate readback.
