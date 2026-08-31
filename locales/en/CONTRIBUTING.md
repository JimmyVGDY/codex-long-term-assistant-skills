# Contributing guide

Chinese version: [CONTRIBUTING.md](CONTRIBUTING.md)

Thank you for contributing to the Codex Cross-Project Engineering Assistant. Every change should preserve safety boundaries, bilingual consistency, and rollback capability.

## Before starting

1. Search existing Issues and Pull Requests to avoid duplicate work.
2. A defect report should include a minimal reproduction, actual result, expected result, and environment details.
3. Open an Issue before a substantial behavior change to define scope, compatibility, and validation evidence.
4. Never place vulnerabilities or sensitive information in a public Issue. Follow the [security policy](SECURITY.en.md).

## Development conventions

- Create a short-lived branch from `main`; recommended prefixes are `feat/`, `fix/`, `docs/`, `test/`, and `ci/`.
- Keep changes minimal and sufficient. Do not bundle unrelated refactors, dependency upgrades, or formatting.
- Provide separate Chinese and English natural-language documents. Use clean paired Chinese/English blocks for source comments and docstrings.
- Do not hard-code a model or reasoning effort in Reviewer TOML files.
- Do not weaken `execution_authorization=NONE`, the Terra High automatic ceiling, project isolation, the hash chain, or privacy boundaries.
- When adding runtime files, update the matching tests, English coverage, and release-build gates.

## Commit format

Commit messages follow:

```text
<type> | <Chinese summary>
```

Common types include `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, and `chore`. Keep each commit single-purpose and independently reversible.

The summary remains Chinese so repository history follows one consistent convention.

## Local validation

```powershell
python scripts\localization-audit.py --strict
python scripts\validate-package.py
```

Changes that affect release construction should also build and verify both reproducible language archives. Mark every skipped check in the Pull Request and describe the remaining risk.

## Pull Request content

A Pull Request should include:

- purpose and scope;
- key implementation details and compatibility impact;
- executed commands and actual results;
- unverified items, risks, and rollback path;
- documentation and bilingual synchronization status.

Merge, release, and deployment are distinct actions. Pull Request approval does not grant release or environment-operation authority.
