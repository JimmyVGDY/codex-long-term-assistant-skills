# V7.2.0 Package and Local Installation Validation Report

Version: 7.2.0

Validation date: 2026-09-02

Package validation and the complete local installation passed. All 151 package tests, 6 runtime tests, and 45 Skill-routing cases passed, together with semantic lint, strict localization, Markdown-link, and payload-manifest checks. Chinese and English release archives each produced byte-identical results across two clean builds.

Native Codex CLI `0.152.1` upgraded the account Plugin from `7.0.0` to `7.2.0` and performed a second complete installation after the final payload was fixed. `install` and `verify` succeeded, `codex plugin list --json` read back `installed=true`, `enabled=true`, and `version=7.2.0`, and no transaction remains active. Source, Marketplace, and Plugin cache each contain 180 managed files with digest `98587b33876c8cbd9cfe9e5918a5915d6ee6213b476aed463e631fc2beb71118`.

Account-level `cp-runtime.py` and `evolution.py` both start and expose their commands. Their installed SHA-256 values match repository sources, closing the prior missing `cp_runtime.evolution` runtime-module gap. Installation verification covers all six Hooks, managed rules, 10 Skills, and 7 Reviewers.

All eleven real-host routing cases ultimately passed, with observations from eleven distinct fresh tasks and exact final-message bytes bound by byte count and SHA-256. The initial 8/11, intermediate 10/11, and final 11/11 evidence sets are retained separately. This proves only the workflows reported in Codex task final output; it does not claim an internal router trace or cryptographic host signature.

Commit, push, tag, GitHub Release, and public artifacts are outside package-validation scope; each state requires its own Git or GitHub readback after the corresponding action.
