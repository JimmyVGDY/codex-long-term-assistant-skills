# V7.14.6 Release Notes

V7.14.6 advances the frozen component-compatibility window used by Codex Desktop to OpenAI's official stable `0.160.1` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal compatibility regression.

- Freeze the current plus ten preceding stable releases from `0.160.1` through `0.155.1`; `0.160.1` enters the active window while `0.155.0` leaves it and remains fail-closed.
- Record the official npm integrity, tarball SHA-256, annotated-tag commit, and source hashes for 0.160.1. Hook discovery/schema and apply_patch handler/context contracts did not drift, so 0.160.1 continues to reuse `result-v158`; 0.155.1 still uses `result-v155`.
- Upstream 0.160.1 backports Windows remote stdio MCP environment preservation, retaining `SYSTEMROOT`, `TEMP`, and `TMP` when remote environment variables are explicitly configured. This fix does not alter this package's reviewer qualification, model defaults, or Operation v2 contract.
- Preserve V7.14.5's bounded package validation, master/tag ancestry gate, Desktop-only layered acceptance, and public-release supply-chain gates.
- The actual Codex Desktop bundled component remains independently accepted through its host contract and a fresh read-only process; the frozen stable window is neither standalone CLI product support nor a Desktop runtime-version claim.

Package validation, account installation, a fresh Desktop process, commit, push, CI, tag, Draft, public Release, and anonymous downloads are read back separately.
