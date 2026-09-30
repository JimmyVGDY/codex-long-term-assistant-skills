<!-- Generated from locales/en/docs/releases/v7.14.2/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.14.2 Release Notes

V7.14.2 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.159.0` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal compatibility regression.

- Freeze the current plus ten preceding stable releases from `0.159.0` through `0.153.3`; `0.153.2` leaves the active window and remains fail-closed.
- Record official npm, `rust-v0.159.0` tag-commit, and source hashes. Hook, schema, and apply_patch contracts match `0.158.0`, so `result-v158` remains in use.
- Upstream adds `instant_interrupt`, refreshed welcome/header/tips, a warnings viewer, plan-time scrolling, expanded Mermaid rendering, and item-anchored thread pagination. It fixes Windows console-window flashes, copy formatting, blank sessions, sign-in, explicit filesystem denials including `.aws`, and macOS TLS/proxy behavior; prompt suggestions and the bundled plugin-creator are removed upstream.
- Make Windows recovery-root containment validation race-safe when concurrent workers create the same selection lock, while retaining lexical containment and per-ancestor link/reparse rejection.
- Preserve the V7.14.1 component boundary and the V7.14.0 authoritative Desktop V2 review-context protocol.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, and anonymous downloads are read back separately.
