<!-- Generated from locales/en/docs/releases/v7.13.2/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.2 Release Notes

V7.13.2 advances the frozen Codex compatibility window to official stable Codex CLI 0.156.1 while retaining the Codex Desktop-only product boundary and all V7.13.1 recovery protections. Upstream 0.156.1 adds GPT-6 Sol and GPT-6 Luna to the model picker and recommends GPT-6 Luna in the rate-limit switch prompt.

- Freeze the current-plus-ten stable window at `0.156.1`, `0.156.0`, `0.155.1`, `0.155.0`, `0.154.0`, `0.153.4`, `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, and `0.152.1`.
- Register the official npm integrity, tarball SHA-256, `rust-v0.156.1` tag commit, and unchanged Hook/apply_patch source-contract digests.
- Preserve frozen V3 as the default reviewer policy. GPT-6 model availability does not activate production defaults, accept native enforcement, or bypass scenario qualification and budget gates.
- Preserve V7.13.1 backup verification, recovery-state retention, exception classification, and installer-test timeout protections.

Commit, push, account installation, CI, tag, Release, assets, provenance, and public effectiveness remain separate readback facts.
