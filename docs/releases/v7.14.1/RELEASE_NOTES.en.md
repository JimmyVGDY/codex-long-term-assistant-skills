<!-- Generated from locales/en/docs/releases/v7.14.1/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.14.1 Release Notes

V7.14.1 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.158.0` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal compatibility regression.

- Freeze the current plus ten preceding stable releases from `0.158.0` through `0.153.2`; `0.153.1` leaves the active window and remains fail-closed.
- Record official npm, `rust-v0.158.0` tag-commit, and source hashes. Hook discovery/schema and context contracts remain unchanged; the changed apply_patch handler is represented by `result-v158`, referenced only by `0.158.0`.
- Upstream adds TUI copy/paste controls, MCP OAuth client secrets, exec-server bearer tokens, transparent image backgrounds, and terminal-input approvals, plus Windows/Linux/macOS sandbox, approval retry, Mermaid, and command-completion fixes. This package records only evidence relevant to Desktop management and runtime boundaries.
- Preserve the V7.14.0 authoritative Desktop V2 review-context protocol, versioned budgets, and delivery receipts.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, and anonymous downloads are read back separately.
