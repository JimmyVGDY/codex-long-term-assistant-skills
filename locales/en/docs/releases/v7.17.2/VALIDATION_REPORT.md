# V7.17.2 Validation Report

The release tag binds commit `d160b0512ffa359c7a8b52ad59eb8424a2642a7f`. Both [PR CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39588208484) and [master CI for the exact commit](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39598793203) completed successfully. The PR merge preview, fix commit and tagged commit have identical Git trees.

Targeted checks passed: eighteen source-recovery, four account-root, two installation-recovery, nineteen task-scope and fifteen context-input tests. The documentation, installation-diagnostics, entrypoint, compatibility and delivery group ran eighty-six tests with one skip; seven additional release tests passed. Bilingual coverage, links, documentation projections, semantic checks and two independent logically read-only reviews passed.

Each [tag-release validation](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39598823547) discovered and executed 1,384 package tests and 265 runtime tests. Final observed results are below, with skips separate and no remaining failures or errors.

| Platform / Python | Package pass / skip | Runtime pass / skip |
| --- | --- | --- |
| Windows / 3.11, second attempt | 1,382 / 2 | 265 / 0 |
| Windows / 3.13 | 1,383 / 1 | 265 / 0 |
| Ubuntu / 3.11 | 1,340 / 44 | 259 / 6 |
| Ubuntu / 3.13 | 1,340 / 44 | 259 / 6 |

The initial Windows / 3.11 run failed the unchanged `test_corrupt_auxiliary_record_does_not_starve_valid_reconciliation` test. Its implementation chain was unchanged, exact-commit master CI passed, and thirteen isolated local reproductions passed. One same-source retry of failed jobs then passed. The existing 250 ms processing window may be affected by runner delays, but the original assertion text was not retained and the precise cause is unconfirmed. Failure evidence was preserved; no assertion was relaxed or check skipped.

At public verification, every retry step including Complete job, the full test logs, build and draft jobs succeeded. The retry job and release-run GitHub summaries still showed `in_progress`. This discrepancy is retained separately; summary success was not fabricated. Publication relied on successfully completed exact-commit full CI, executed release-validation logs and the artifact evidence below.

The [formal release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.17.2) became public at 2026-10-21 15:05:43 UTC. All six assets were anonymously downloaded; sizes and SHA-256 digests match the verified draft. Both ZIPs have byte-identical dual builds, and GitHub attestation binds this repository, release workflow, `refs/tags/v7.17.2` and the exact commit above.

- Chinese ZIP SHA-256: `14ee2f07c8b32cd3b73f84ce1a615c825093996eab2adcbe9f541e673c86bd75`.
- English ZIP SHA-256: `fa35b35b885921658daf412b337f7bcac7992bde11f9cd1233ad94f31b653452`.

Local installation diagnostics returned PASS, all 350 payload files match the formal Chinese package, and the current Desktop session read back genuine parent Hook provenance. Desktop was not restarted. Locator readback does not establish enforced budgets or system-level read-only isolation. Published tags and assets remain immutable; this report was completed after publication.
