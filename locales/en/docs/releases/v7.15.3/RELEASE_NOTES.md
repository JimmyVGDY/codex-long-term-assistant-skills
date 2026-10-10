# V7.15.3 Release Notes

V7.15.3 advances the frozen internal component-compatibility window used by Codex Desktop to OpenAI's official stable `0.162.1` release. Product support remains limited to Codex Desktop; standalone CLI execution is only for management, build, and internal regression.

- Freeze the current plus ten preceding stable releases from `0.162.1` through `0.157.0`; `0.162.1` and `0.162.0` enter while `0.156.1` and `0.156.0` leave and remain fail-closed.
- Record official npm integrity, tarball SHA-256, annotated-tag commits, and source hashes. The 0.162.x Hook discovery and schema retain the 0.161.0 contracts, while the apply_patch handler changed again, so this release adds `result-v162`; context did not drift.
- Remove now-unused `result-v155` after 0.155.1 leaves; retained releases continue to use their frozen `result-v158` and `result-v156` profiles.
- Upstream adds GPT-6.1 Sol catalog defaults, terminal MCP login, voice-device selection, and gated Daybreak/Cyber entry points, with permission, recovery, and retry fixes. These changes do not automatically alter this package's model routing, reviewer qualification, budgets, or Operation v2 contract.
- Package validation, account Plugin, an actual fresh Desktop task, commit, push, CI, annotated tag, Draft, publication, and anonymous downloads remain separate readbacks.
