# V7.2.0 Package and Local Installation Validation Report

Chinese: [VALIDATION_REPORT.md](VALIDATION_REPORT.md)

Version: 7.2.0

Validation date: 2026-09-02

## Current status

Package validation and the complete local installation both passed:

- All 151 package tests, 6 runtime tests, and 45 Skill-routing cases passed, together with semantic lint, strict localization, Markdown-link, and payload-manifest checks.
- Chinese and English release archives each completed two clean builds with byte-identical results per locale.
- Native Codex CLI `0.152.1` upgraded the account Plugin from `7.0.0` to `7.2.0` and performed a second complete installation after the final payload was fixed; both `install` and `verify` succeeded and no upgrade transaction remains active.
- `codex plugin list --json` read back the target Plugin with `installed=true`, `enabled=true`, and `version=7.2.0`.
- Source, Marketplace, and Plugin cache each contain 180 managed payload files with the same digest: `98587b33876c8cbd9cfe9e5918a5915d6ee6213b476aed463e631fc2beb71118`.
- Account-level `cp-runtime.py` and `evolution.py` both start and expose their complete command entry points. Each installed file has the same SHA-256 as its repository source, closing the prior missing `cp_runtime.evolution` runtime-module gap.
- Account state records a passing `codex-cli 0.152.1` capability probe and no active transaction. Installation verification covers all six Hooks, managed rules, 10 Skills, and 7 Reviewers.
- All eleven real-host routing cases ultimately passed, with eleven observations from distinct fresh tasks and exact final-message bytes bound by byte count and SHA-256. Evidence for the initial 8/11 result, intermediate 10/11 result, and final 11/11 result is retained separately.

The real-host conclusion proves only the activated workflows reported in Codex task final output. It does not claim an internal router trace or a cryptographic host signature; this limitation must accompany the 11/11 result even though it does not weaken package tests or installation-identity readback.

## Fixed acceptance gates

- Manifest, Plugin, payload, and release-script versions agree
- Focused tests and full package/runtime suites pass
- Chinese and English archives are byte-identical across two clean builds
- Local `install --scope user --mode plugin` and `verify` pass
- `codex plugin list --json` reads back `installed=true`, `enabled=true`, and `version=7.2.0`
- Account-level `cp-runtime.py` and `evolution.py` run, while all six Hooks and managed global rules load consistently
- Real-host routing acceptance passes 11/11, with a distinct task ID, timezone-aware timestamp, and hash-bound raw final message for every case

Commit, push, tag, GitHub Release, and public artifacts are outside package-validation scope; each state requires its own Git or GitHub readback after the corresponding action.
