# V7.4.4 Validation Report

Status: local package-only validation passed. Remote push, tag, CI, Draft, and publication have not occurred yet. No real-account installation was run for V7.4.4.

## Local validation

- `python scripts/validate-package.py`: 237 package tests and 6 runtime tests passed with package-only scope on Python 3.13.15; the minimum remains Python 3.11.
- `tests.test_release_automation`: 10 tests passed; the post-repair focused run passed 12 tests including two English-package boundary cases.
- Strict localization audit: 778 tracked files, 770 text files, 526 documents, 118 code files, 126 structured files, and zero findings.
- Repository-wide link audit: 524 Markdown files, 596 links, zero findings, and zero warnings.
- Semantic lint, `git diff --check`, and Plugin payload verification passed. The payload contains 182 files with digest `7c9932a088275f27724578035fca08c453bfb69e40426eb224551ce6717bd138`.
- The Codex compatibility registry covers 11 frozen stable releases; the Windows/Ubuntu remote matrix remains a separate tag-CI gate.

## Independent review and historical backfill

The functional/business and security reviewers reported zero findings in round one. The delivery reviewer's evidence-index and recovery-runbook findings were repaired together and confirmed in round two; no code finding remains. Isolation was logical-readonly, not system-readonly. Runtime model identity was not exposed, so only approved profiles are recorded.

Releases v7.3.0, v7.4.0, v7.4.1, v7.4.2, and v7.4.3 were changed from exact generic titles to their respective themes and read back individually; v7.2.0 and earlier were unchanged. Five before/after checks confirmed that `body_sha256`, assets, draft, prerelease, and published_at were unchanged. See [`HISTORICAL_RELEASE_BACKFILL.json`](HISTORICAL_RELEASE_BACKFILL.json).

## Pending remote scope

- push and remote readback of `main`;
- the annotated `v7.4.4` tag and its peeled commit;
- the GitHub Actions Windows/Ubuntu matrix, provenance, and Draft-only behavior;
- download, digest, and candidate verification of all six Draft assets;
- public Release title, state, body, and asset readback.

Package-only evidence must not be interpreted as proof of CI, remote assets, public publication, or real-account installation.
