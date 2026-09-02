# V7.3.0 Package and Local Installation Validation Report

Chinese: [VALIDATION_REPORT.md](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/v7.3.0/VALIDATION_REPORT/)

Version: 7.3.0

Validation date: 2026-09-02

## Current status

Package and local pre-release validation passed: all 170 package tests, 6 runtime tests, and 45 Skill-routing regressions passed, together with semantic, localization, Markdown-link, payload-identity, and zero-side-effect workspace gates. Chinese and English release archives each completed two clean builds with byte-identical results per locale.

The V7.3.0 payload is fixed at 180 managed files with digest `4f0168e4014440185a958f207931d01e73e4ca73207ee318ed0fcbee2a85a6d0`. The account-level forced upgrade identified `from_version=7.2.0` and `to_version=7.3.0`; managed backup, installation, and verify all succeeded. Marketplace and versioned Plugin-cache file counts and digests match the source, and no upgrade transaction remains active.

The real calibration observation retains three finalized records from one distinct task with complete cost coverage. Both Reviewer signals remain `INSUFFICIENT_DATA`, no routing proposal is generated, and default profiles remain unchanged. This proves fail-closed behavior and data semantics, not a yield conclusion at a larger sample size.

`codex plugin list --json` read back `installed=true`, `enabled=true`, and `version=7.3.0`. After publication, the downloaded ZIP still requires independent provenance, digest, package-structure, reinstall, and readback verification.

## Fixed acceptance gates

- Manifest, Plugin, payload, validators, release scripts, and bilingual current documentation agree on the version
- Full package/runtime suites and all 45 routing regressions pass
- Chinese and English archives each build twice with byte-identical results per locale
- User-level Plugin forced reinstall and verify pass locally
- `codex plugin list --json` reads back 7.3.0 as installed and enabled
- Public assets pass GitHub Artifact Attestations, SHA256SUMS, build-witness, and post-download reinstall checks

Commit, push, tag, GitHub Release, and public artifacts are outside package-validation scope. Each state requires independent Git, GitHub, or local-installation readback after its corresponding action.
