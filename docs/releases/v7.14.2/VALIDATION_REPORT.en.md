<!-- Generated from locales/en/docs/releases/v7.14.2/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.14.2 Validation Record

- npm `latest` and GitHub `rust-v0.159.0` both identify `0.159.0` as a non-prerelease stable release.
- The npm integrity, tarball SHA-256, exact CLI-output digest, and official tag commit `687a119f0fcaace47e1f1abcc77cec6c813fd6da` were read independently.
- Hook discovery/schema, apply_patch handler, and context hashes match `0.158.0`; both versions use the frozen `result-v158` profile.
- Full package validation passed with 815 package tests and 231 runtime tests. The 0.159.0 fixed artifact, CLI contract, isolated Plugin, and synthetic Hook matrix passed.
- The first full run exposed one unrelated runtime timing failure. Its isolated case passed three times, but a later full run reproduced a Windows root-selection race in a different package test. The containment check was made race-safe without weakening the lexical and reparse-point gates; 200 repeated concurrency runs and the final complete 815+231 run passed.
- The account management CLI read back `0.159.0`; Plugin install, verify, and doctor read back `7.14.2` and `HOST_COMPATIBLE`. A new read-only ephemeral Desktop bundled-component process `0.158.0-alpha.2.1` returned `DESKTOP_ACCEPTANCE_PASS`.
- CI, annotated tag, Draft, six assets, SHA256SUMS, witnesses, provenance, public Release, and anonymous downloads remain separate gates.
