# V7.14.1 Validation Record

- npm `latest` and GitHub `rust-v0.158.0` both identify `0.158.0` as a non-prerelease stable release.
- The npm integrity, tarball SHA-256, tag commit `064c6b8c737f5b41d171fdda80bd9ef10ad06eb3`, Windows binary, and CLI-output digests were read independently.
- Hook discovery/schema and context hashes remain unchanged; the apply_patch handler change is frozen as `result-v158`.
- Full validation passed with 815 package tests and 231 runtime tests. The 0.158.0 isolated Plugin, CLI contract, and synthetic Hook matrix passed.
- The account management CLI read back `0.158.0`. Plugin installation, verify, and doctor read back `7.14.1` and `HOST_COMPATIBLE`. A newly started bundled Desktop component `0.158.0-alpha.2.1` returned `DESKTOP_ACCEPTANCE_PASS` in a read-only ephemeral process.
- CI, tag, Draft, six assets, SHA256SUMS, witnesses, provenance, public Release, and anonymous downloads remain separate gates.
