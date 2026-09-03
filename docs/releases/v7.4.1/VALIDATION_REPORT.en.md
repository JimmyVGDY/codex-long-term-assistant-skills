# V7.4.1 Validation Report

Status: package validation passed. The evidence below does not claim commit, push, or publication.

- Registry digest: `1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8`.
- All eleven pinned official npm packages passed `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS` locally on Windows.
- Window: 0.153.0, 0.152.1, 0.152.0, 0.151.0, 0.150.1, 0.150.0, 0.149.1, 0.149.0, 0.148.0, 0.147.0, and 0.146.1.
- Focused regressions cover schema-3 host binding, drift to another supported version, unknown-host denial, legacy Marketplace repair, and unknown metadata preservation.
- The full regression passed 218 package tests and 6 runtime tests. Reproducible bilingual builds, runtime localization coverage, and 525 repository links also passed.
- Final independent compatibility-regression and data-contract reviews passed with no findings in the frozen packet.
- A forced user-level reinstall passed on Codex 0.153.0. The state migrated to schema 3, and Plugin activation, host binding, and source/Marketplace/cache payload digests matched on readback.

Remaining: GitHub Windows/Ubuntu matrix, a native 0.153.0 account task and Hook acceptance, commit, push, and public release.
