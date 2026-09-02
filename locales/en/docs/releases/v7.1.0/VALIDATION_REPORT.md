# V7.1.0 Package and Local Installation Validation Report

Version: 7.1.0

Validation date: 2026-09-02

Package validation and the complete local installation passed. All 130 package tests, 6 runtime tests, and 45 Skill-routing cases passed, together with semantic lint, strict localization, Markdown-link, and payload-manifest checks. Chinese and English release archives each produced byte-identical results across two clean builds.

Native Codex CLI `0.152.1` upgraded the account Plugin from `7.0.0` to `7.1.0`; `install` and `verify` succeeded, `codex plugin list --json` read back `installed=true`, `enabled=true`, and `version=7.1.0`, and no transaction remains active. Source, Marketplace, and Plugin cache each contain 182 managed files with digest `b9b4fa3d957dd4b58094c7aac50fac38ec484405ce28369583d094609750db4d`.

Account-level `cp-runtime.py` and `evolution.py` both start and expose their commands. Their installed SHA-256 values match repository sources, closing the prior missing `cp_runtime.evolution` runtime-module gap. Installation verification covers all six Hooks, managed rules, 10 Skills, and 7 Reviewers.

Commit, push, tag, GitHub Release, and public artifacts are outside package-validation scope; each state requires its own Git or GitHub readback after the corresponding action.
