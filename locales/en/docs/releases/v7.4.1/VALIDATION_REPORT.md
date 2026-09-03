# V7.4.1 Validation Report

Status: package, user-level installation, cross-platform GitHub, and real-account acceptance passed for the final candidate. The final main, tag, and public Release states still require post-publication readback.

- Registry digest: `1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8`.
- Compatibility window: 0.153.0, 0.152.1, 0.152.0, 0.151.0, 0.150.1, 0.150.0, 0.149.1, 0.149.0, 0.148.0, 0.147.0, and 0.146.1.
- All eleven pinned official npm packages passed local Windows `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS` cells.
- Focused regressions cover schema-3 host binding, supported-version drift, unknown-host denial, legacy Marketplace repair, and unknown metadata preservation.
- The full regression passed 224 package tests and 6 runtime tests. Strict bilingual audit, reproducible bilingual builds, and 533 links across 494 tracked Markdown files also passed.
- Final independent compatibility-regression and data-contract reviews passed with no findings in frozen packet `6fdd3cc363b77715b7852dc398ac0290c5453778d155b205ec5dc444c419573f`.
- A forced user-level reinstall passed on Codex 0.153.0. Schema 3, Plugin activation, host binding, and the source/Marketplace/cache payload digest all matched on readback: `7fe0aeba4d5d675b2c80ac384a8bd58025c9965fba2a64cafedd047b56ca3b39`.
- GitHub Actions run [33741685461](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33741685461) completed successfully for candidate commit `181f5225dccc27abf5dd49712962514f936c5185`, covering the Windows/Ubuntu eleven-version compatibility matrix, four package-validation cells, and provenance build.
- Native read-only acceptance on Codex 0.153.0 completed a Luna Low parent/child Agent journey and returned exactly `V741_REAL_HOST_PASS`. The machine report confirmed seven events in order: `TURN_OPENED`, `PRE_TOOL_GUARD`, `SUBAGENT_STARTED`, child `TURN_OPENED`, `SUBAGENT_STOPPED`, `TASK_COMPLETED`, and `SESSION_ENDED`; the requested-model gate was `PASS`.
- Ordinary Hook payloads did not supply trusted host model attestation, so actual subagent-model evidence remains `UNAVAILABLE`. DPAPI sealing was also `UNAVAILABLE` in the real read-only sandbox. `SESSION_ENDED` was persisted with `seal_required=true`, and Evolution correctly failed closed on the unsealed tail instead of treating it as consumable data.

Pending publication readback: the remote main commit, `v7.4.1` tag, tagged workflow artifacts/provenance, and public Release.
