# V7.13.4 Release Notes

V7.13.4 fixes Windows installation permissions and delegation entry points in Codex Desktop. The product supports the Desktop app only. Existing stable-component records remain internal contract-regression references; they do not define standalone CLI support or Desktop version admission.

- Preserve the destination parent's read access when installing public Plugin, Hook, and runtime payloads without adding write permission. Private state and restoration copies retain their existing rules.
- Exclude generated Python bytecode so public runtime deployment matches the release payload.
- Normalize bare, dotted, and Desktop-concatenated delegation tool names, and register complete names in one Pre/Post handler group to avoid missed or duplicate handling.
- Preserve Windows path identity, recovery safeguards, frozen V3 defaults, and GPT-5.6 compatibility. The nine GPT-6 candidates remain subject to scenario qualification and real evidence.

Actual Desktop installation, ordinary-sandbox reads with writes denied, and V4 message-reentry rejection were verified. Positive creation still fails before execution with `V4_REQUEST_MESSAGE_MISMATCH`: this host supplies an opaque encrypted message without a verified plaintext-binding interface. A controlled plaintext-rewrite experiment also produced a decoding error and was not adopted. This release does not bypass validation, synthesize receipts, enable GPT-6 defaults, or claim model qualification or positive native admission.

Existing component samples from 0.157.0 through 0.153.0 and their official artifact/source digests remain internal references. They are not the Desktop app's supported-version window; acceptance must use the actual running Desktop component.

Commit, push, installation, CI, tag, Release, assets, provenance, and public effectiveness require separate readback. Full model-performance evaluation, reasoning-effort gains, and default migration remain unfinished follow-up work.
