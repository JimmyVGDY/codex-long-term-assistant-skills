<!-- Generated from locales/en/docs/releases/v7.14.5/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.14.5 Validation Record

- npm `latest` and GitHub `rust-v0.160.0` both identify `0.160.0` as a non-prerelease stable release.
- npm integrity `sha512-kEtV...lpjg==`, tarball SHA-256 `373517768e912eeb5054024ae9215e2c90a1420957b66fe134ef745a00948d4a`, and annotated-tag commit `a956835d020762cb2b570053af06f643a11c0ecc` were read independently.
- Hook discovery/schema, apply_patch handler, and context hashes are `fd05ee...72b04`, `162735...3e14`, `75cc61...0cad`, and `9a9acc...e00cc`, matching the current `result-v158` contract.
- The registry contains exactly the eleven releases from `0.160.0` through `0.155.0`; 0.160.0 uses `result-v158`, while 0.154.0 and its now-unused `result-v154` profile leave the window.
- The 0.160.0 isolated CLI/Plugin/Hook cell passed; full validation passed 816 package tests and 231 runtime tests. Strict bilingual, link, documentation-projection, and MkDocs builds passed. Repository-external witnesses confirmed both locale packages were byte-reproducible; the tag workflow regenerates and binds the final asset digests.
- The account management CLI read back `0.160.0`. Plugin install/verify/strict doctor read back `7.14.5`, `installed=true`, `enabled=true`, matching payload digests, and `HOST_COMPATIBLE`. A fresh ephemeral read-only process from the actual Codex Desktop bundled component `0.160.0` returned `DESKTOP_ACCEPTANCE_PASS`.
- Logical-readonly pre-review adopted the atomic `result-v154` removal regression and rejected a proposal that would conflate the stable window with the actual Desktop host contract; post-review is recorded separately.
- CI, annotated tag, Draft, six assets, SHA256SUMS, witnesses, provenance, public Release, and anonymous downloads remain separate gates read back outside the source snapshot.
