<!-- Generated from locales/en/docs/releases/v7.13.5/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.5 Validation Record

- npm `latest` and GitHub `rust-v0.157.1` both identify `0.157.1` as a non-prerelease stable release; the official Release provides no verifiable feature highlights.
- The npm integrity, tarball SHA-256, official tag commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`, Windows binary digest, and exact CLI output digest were read independently.
- Official Hook discovery, Hook schema, and apply_patch handler/context hashes match `0.157.0`; all eleven registry tags and source records were rechecked.
- Full package validation passed with 780 package tests and 231 runtime tests. The 0.157.1 isolated Plugin, CLI contract, and synthetic Hook matrix passed.
- Account-global Codex read back `0.157.1`. After reinstallation, doctor returned `PASS` and the Plugin read back `7.13.5`, `installed=true`, and `enabled=true`. A newly started bundled Desktop component `0.158.0-alpha.2.1` returned `DESKTOP_ACCEPTANCE_PASS` in a read-only ephemeral process.
- CI, tag, Draft, six assets, SHA256SUMS, witnesses, provenance, public Release, and anonymous downloads remain separate gates.
