<!-- Generated from locales/en/docs/releases/v7.13.4/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.4 Release Notes

V7.13.4 advances the frozen compatibility window to official stable Codex CLI 0.157.0 while preserving the Codex Desktop-only product boundary and V7.13.3 Windows path-identity fix.

- Freeze the eleven-version window at 0.157.0 through 0.153.0; 0.152.1 leaves the active window.
- Register official npm integrity, tarball SHA-256, tag commit `00c972ed5d6ff6499317fd41b7f23605b8e6850d`, and unchanged Hook/apply_patch source hashes using `result-v156`.
- Track upstream GPT-6 Sol/Luna catalog and Bedrock support, fullscreen transcripts, automatic background-server startup, conversation forking/import, rendering improvements, and network/voice/upload fixes.
- Preserve frozen V3 defaults, GPT-5.6 compatibility, V7.13.1 recovery protection, and V7.13.3 normalized Windows root identity.
- Preserve inherited read-only ACLs when deploying public Plugin/runtime payloads, while keeping state, backups, and Marketplace metadata private.
- Normalize Desktop collaboration tool names and register explicit bare, dotted, and concatenated Pre/Post matcher alternatives without wildcard production matchers.

Native V4 reentry denial is verified. Positive native admission remains blocked because Desktop transports the message body as an opaque encrypted value; exact plaintext body binding is therefore unverified. This release does not weaken body validation, synthesize receipts, activate GPT-6 defaults, or claim model qualification/native positive PASS.

Commit, push, installation, CI, tag, Release, assets, provenance, and public effectiveness remain separate readback facts.
