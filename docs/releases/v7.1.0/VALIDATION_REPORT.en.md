# V7.1.0 Package and Local Installation Validation Report

Chinese: [VALIDATION_REPORT.md](VALIDATION_REPORT.md)

Version: 7.1.0

Validation date: 2026-09-02

## Current status

Package validation and the complete local installation both passed:

- All 130 package tests, 6 runtime tests, and 45 Skill-routing cases passed, together with semantic lint, strict localization, Markdown-link, and payload-manifest checks.
- Chinese and English release archives each completed two clean builds with byte-identical results per locale.
- Native Codex CLI `0.152.1` upgraded the account Plugin from `7.0.0` to `7.1.0`; both `install` and `verify` succeeded and no upgrade transaction remains active.
- `codex plugin list --json` read back the target Plugin with `installed=true`, `enabled=true`, and `version=7.1.0`.
- Source, Marketplace, and Plugin cache each contain 182 managed payload files with the same digest: `b9b4fa3d957dd4b58094c7aac50fac38ec484405ce28369583d094609750db4d`.
- Account-level `cp-runtime.py` and `evolution.py` both start and expose their complete command entry points. Each installed file has the same SHA-256 as its repository source, closing the prior missing `cp_runtime.evolution` runtime-module gap.
- Account state records a passing `codex-cli 0.152.1` capability probe and no active transaction. Installation verification covers all six Hooks, managed rules, 10 Skills, and 7 Reviewers.

## Fixed acceptance gates

- Manifest, Plugin, payload, and release-script versions agree
- Focused tests and full package/runtime suites pass
- Chinese and English archives are byte-identical across two clean builds
- Local `install --scope user --mode plugin` and `verify` pass
- `codex plugin list --json` reads back `installed=true`, `enabled=true`, and `version=7.1.0`
- Account-level `cp-runtime.py` and `evolution.py` run, while all six Hooks and managed global rules load consistently

Commit, push, tag, GitHub Release, and public artifacts are outside package-validation scope; each state requires its own Git or GitHub readback after the corresponding action.
