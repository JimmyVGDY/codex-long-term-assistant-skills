# V7.14.3 Validation Record

- npm `latest` and GitHub `rust-v0.159.2` both identify `0.159.2` as a non-prerelease stable release.
- npm integrity, tarball SHA-256, exact CLI-output digests, and official tag commits `8e68a98ef03cdde76d2e6800791ebdf1b3b95b24` (0.159.1) and `ff6aec96948b70d94983af2641a6b67c94faeff5` (0.159.2) were read independently.
- Hook discovery/schema, apply_patch handler, and context hashes match `0.159.0`; all three `0.159.x` releases use the frozen `result-v158` profile.
- Isolated Windows CLI/Plugin/Hook cells passed for both 0.159.1 and 0.159.2. Full package validation passed with 815 package tests and 231 runtime tests.
- The account management CLI read back `0.159.2`; Plugin install, verify, and doctor read back `7.14.3` and `HOST_COMPATIBLE`. A new read-only ephemeral Desktop bundled-component process `0.158.0-alpha.2.1` returned `DESKTOP_ACCEPTANCE_PASS`.
- CI, annotated tag, Draft, six assets, SHA256SUMS, witnesses, provenance, public Release, and anonymous downloads remain separate gates.
