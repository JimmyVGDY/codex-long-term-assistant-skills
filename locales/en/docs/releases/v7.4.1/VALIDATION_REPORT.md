# V7.4.1 Validation Report

Status: package validation passed; this is not commit, push, or publication evidence.

- Registry digest: `1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8`.
- All eleven pinned official npm packages passed local Windows CLI, isolated Plugin, and synthetic Hook cells.
- Focused regressions cover schema-3 host binding, supported-version drift, unknown-host denial, legacy Marketplace repair, and unknown metadata preservation.
- The full regression passed 218 package tests and 6 runtime tests. Reproducible bilingual builds, runtime localization coverage, and 525 repository links also passed.
- Final independent compatibility-regression and data-contract reviews passed with no findings in the frozen packet.
- A forced user-level reinstall passed on Codex 0.153.0. The state migrated to schema 3, and Plugin activation, host binding, and source/Marketplace/cache payload digests matched on readback.

Remaining gates are the GitHub Windows/Ubuntu matrix, a native 0.153.0 account task and Hook acceptance, commit, push, and publication.
