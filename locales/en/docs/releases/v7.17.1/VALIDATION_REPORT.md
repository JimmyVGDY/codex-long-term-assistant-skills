# V7.17.1 Validation Record

## Official baseline and frozen evidence

- The official OpenAI changelog, npm `latest`, and the latest GitHub Release identify 0.163.0 / `rust-v0.163.0` as a non-prerelease stable release.
- Tag commit: `83086188ae0614bd882818ff1aa23f3194962012`.
- npm tarball SHA-256: `1a71db36560bb446d2c2e63ae675c4a3018c38ace38ca533f8d1b25d3e6555b4`.
- Discovery: `763704f5ae5f227d186dae8f5339edd6fde4f4a54c88c8ffb5ef9ad1b5a368eb`; schema: `162735b4d0c021c911cb3939b6130d2aad90cf5f865069a17b97c0cf02c53e14`; apply_patch handler: `1256b2219f6acb9c49ae472860ee69d73c75bb427dcca4dae2a30018d30216c0`; context: `9a9acc6daab2112bd9ca1a07a1e1f2105b20a7f565878157c726ee0d7a3e00cc`.
- The closed window is 0.163.0, 0.162.1, 0.162.0, 0.161.0, 0.160.1, 0.160.0, 0.159.2, 0.159.1, 0.159.0, 0.158.0, and 0.157.1; the ordered digest is `de1b6a2ab6d51be3a437d241afbee22572b9bf9ee2c3bb51e04bec01872153f6`.

## Current source-snapshot validation

- Compatibility registry contract: 18 checks passed.
- package-manager doctor window readback: passed.
- Isolated 0.163.0 Windows CLI / Plugin / synthetic Hook matrix: passed; the artifact digest matches the frozen registry.
- The baseline was updated from V7.16.2 to post-release V7.17.0 commit `fd43b7dc273d11cd4a9f06bde105986c4b63711a`; all earlier evidence is therefore stale by rule and will be rerun.

Full package, runtime, documentation, reproducible-build, cross-platform matrix, independent review, account installation, actual Desktop process, commit, push, tag, Release, signed assets, and public downloads remain separate gates. They are marked passed only after direct execution and readback.

## Complete local validation

- Package evidence: 1,359 tests discovered and executed; 1,358 passed and one was platform-skipped, with no failure or error. Report SHA-256: `da95c3e0f74baad4653aeb8d6f71a293e2307cc52cfbd4b9a02b791715a36157`.
- Runtime evidence: 265 tests discovered and executed; all passed. Report SHA-256: `0e756adafd9ae2ad87d5408a439010e001a22c0d83d777d8f875fbc4db951e47`.
- All 23 required capability projections mapped by `validation_evidence.py` are `PASS`.
- The local Windows PowerShell defaults prohibit script execution. Installer and unified-CLI cases passed after setting `PSExecutionPolicyPreference=Bypass` only for the validation child process. Machine-level policy was not changed; this environment difference is retained separately and is not described as a product fix.

## Official-source and reproducible-build validation

- All eleven official tags in the closed window, plus discovery, schema, apply_patch handler, context digests, and frozen assertions were replayed online. The result is `PASS`; the repository-external report is retained in the local temporary evidence directory.
- Both locale builders produced identical internal two-run digests. Independent archive verification and byte-for-byte comparison across separate calls passed; each archive contains 946 entries.
- One extra Chinese build attempt failed because a temporary file disappeared before replacement. The transient failure is retained; the retry passed and was byte-identical to the successful archive.
- Final tag assets, SHA256SUMS, both witnesses, and provenance are produced by the tag workflow after commit and must be read back after public publication. Source documentation does not embed a prebuild ZIP digest that would change its own archived content.
