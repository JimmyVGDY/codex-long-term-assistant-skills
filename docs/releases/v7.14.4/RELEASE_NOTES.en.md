<!-- Generated from locales/en/docs/releases/v7.14.4/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.14.4 Release Notes

V7.14.4 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.159.2` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal compatibility regression.

- Freeze the current plus ten preceding stable releases from `0.159.2` through `0.154.0`; both `0.159.1` and `0.159.2` enter the active window while `0.153.4` and `0.153.3` leave it and remain fail-closed.
- Record official npm, annotated tag commits, and source hashes for both patch releases. Hook discovery/schema and apply_patch handler/context contracts match `0.159.0`, so all three `0.159.x` versions continue to reuse `result-v158`.
- Upstream 0.159.1 adds GPT-6.1 Sol to bundled and Amazon Bedrock catalogs, without changing this package's frozen reviewer qualification or production defaults. Upstream 0.159.2 backports Windows console-window suppression for background and sandboxed commands.
- Raise the bounded package-validation subprocess timeout from 1800 to 3600 seconds after GitHub Actions run `36846683350` attempts 1-3 timed out on Windows Python 3.11 without an assertion failure; timeout still produces fail-closed evidence.
- Preserve the V7.14.3 Desktop-only compatibility boundary, master/tag ancestry gate, Windows recovery-root race fix, and the V7.14.0 authoritative Desktop V2 review-context protocol.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, and anonymous downloads are read back separately.
