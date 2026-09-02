# V7.1.0 Release Notes

Version: 7.1.0

## Key changes

- The current Codex CLI compatibility baseline is 0.152.1. The installer retains verified 0.150.1 compatibility and fails closed for other unverified versions.
- Plugin Marketplace commands and the core `plugin list --json` fields were checked on native Windows Codex CLI 0.152.1.
- Plugin and standalone installations transactionally install, verify, and remove the account-level `cp-runtime.py` and `evolution.py` tools.
- Restricted tasks resolve the exact current Plugin cache from installation state when the account runtime is unreadable.
- Current metadata, builds, verification, attestations, and operating documentation are synchronized to 7.1.0 with a declared 7.0.0 upgrade path.

Package validation, local installation, remote publication, and post-download verification remain separate evidence boundaries.
