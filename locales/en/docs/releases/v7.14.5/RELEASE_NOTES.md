# V7.14.5 Release Notes

V7.14.5 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.160.0` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal compatibility regression.

- Freeze the current plus ten preceding stable releases from `0.160.0` through `0.155.0`; `0.160.0` enters the active window while `0.154.0` leaves it and remains fail-closed.
- Record the official npm integrity, tarball SHA-256, annotated-tag commit, and source hashes for 0.160.0. Hook discovery/schema and apply_patch handler/context contracts match the 0.159.x line, so the release continues to reuse `result-v158` and removes `result-v154`, whose only consumer left the window.
- Upstream 0.160.0 adds workspace defaults for projectless sessions and queued-message recovery, fixes Windows sandbox, long-path permission, and background-console behavior, and caches Plugin manifests and remote connections. These changes do not alter this package's reviewer qualification, model defaults, or Operation v2 contract.
- Preserve V7.14.4's 3600-second bounded package validation, master/tag ancestry gate, Desktop-only layered acceptance, and public-release supply-chain gates.
- The actual Codex Desktop bundled component remains independently accepted through its host contract and a fresh read-only process; the frozen stable window is neither standalone CLI product support nor a Desktop runtime-version claim.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, and anonymous downloads are read back separately.
