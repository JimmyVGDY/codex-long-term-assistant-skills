<!-- Generated from locales/en/docs/releases/v7.1.0/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.1.0 Release Notes

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/v7.1.0/RELEASE_NOTES/)

Version: 7.1.0

## Key changes

- The current Codex CLI compatibility baseline is 0.152.1. The installer retains verified 0.150.1 compatibility and continues to fail closed for other unverified versions.
- Plugin Marketplace add/remove/list commands and the core `plugin list --json` fields were checked on native Windows Codex CLI 0.152.1.
- Plugin and standalone installations now transactionally install, verify, and remove the account-level `cp-runtime.py` and `evolution.py` tools.
- When the account runtime is unreadable in a restricted task, the launchers resolve the exact current Plugin cache from installation state without guessing across versions.
- Manifest, Plugin metadata, bilingual builds, release verification, attestations, and current operating documentation are synchronized to 7.1.0, with a declared 7.0.0 upgrade path.

## Unchanged safety boundaries

- `execution_authorization=NONE`
- Plugin installation still fails closed on unverified Codex CLI versions
- Skill activation does not expand file, Git, environment, production, or data authority
- The automatic sub-agent ceiling remains `gpt-5.6-terra + high`

## Acceptance boundary

Package validation, a complete local 0.152.1 Plugin installation, remote publication, and post-download artifact verification are recorded separately. A PASS at one stage does not substitute for readback at another.
