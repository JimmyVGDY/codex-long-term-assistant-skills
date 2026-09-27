# V7.13.5 Release Notes

V7.13.5 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.157.1` release. Product support remains limited to Codex Desktop; standalone CLI executables are used only for management, build, and compatibility regression and do not establish a standalone CLI product or acceptance track.

- Freeze the current plus ten preceding stable releases: `0.157.1`, `0.157.0`, `0.156.1`, `0.156.0`, `0.155.1`, `0.155.0`, `0.154.0`, `0.153.4`, `0.153.3`, `0.153.2`, and `0.153.1`. Version `0.153.0` leaves the active window and remains fail-closed.
- Record the official npm integrity, tarball SHA-256, `rust-v0.157.1` tag commit, and source-contract hashes. Hook discovery, Hook schema, and apply_patch result contracts match `0.157.0`, so `result-v156` remains in use.
- Upstream describes this as a maintenance release and provides no verifiable feature highlights; this release does not infer specific upstream fixes.
- Preserve the V7.13.4 Windows Desktop permission, delegation, recovery, path-protection, and fail-closed native-admission boundaries.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, assets, and anonymous downloads are read back separately.
