# V7.16.2 Validation Report

This version was [published](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.16.2) on 2026-10-15 at 11:22:13 UTC. Its tag binds commit `2604e8bea96294c696106935186ebeab1df9a0e4`. The [release workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38717892798) passed all four complete validation jobs, signed builds and draft-asset checks.

## Release validation results

| Platform and Python | Package passed / skipped | Runtime passed / skipped |
|---|---:|---:|
| Windows / 3.11.9 | 1243 / 2 | 239 / 0 |
| Windows / 3.13.16 | 1244 / 1 | 239 / 0 |
| Ubuntu / 3.11.17 | 1203 / 42 | 233 / 6 |
| Ubuntu / 3.13.16 | 1203 / 42 | 233 / 6 |

Each job covered 1245 package tests and 239 runtime tests, with zero failures or errors. Skipped cases retain their original status and are not counted as passes. PR and post-merge master CI also passed. Earlier failed local-candidate reports remain unchanged rather than being relabeled as passing.

Each language package was built twice with identical bytes in the release environment. Independent provenance verification bound the repository, release workflow, tag, source commit and hosted runner. All six public assets were downloaded anonymously and compared byte for byte with the signed candidate. Digests are in the [checksum file](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.16.2/SHA256SUMS.txt).

The native-tested local archives and formal ZIPs have different compressed digests, but all 903 files in each language package contain identical bytes. Public asset digests are authoritative. Source payload and installed readers match, and local acceptance is reused only for identical file contents.

## Targeted regressions

- `test_g6_allowance_budget`: atomic spending, role/profile isolation, old prefixes, unknown calls, no-start retries, required holds and settlement after closure.
- `test_g6_allowance_authority`: isolated native-format records, human-source metadata, direct/structured replies, quotation rejection, duplicate/concurrent processing, post-append interruption, file replacement and large-record recovery.
- `test_g6_allowance_workflow`: real scripts and Hook subprocesses covering exhaustion through approval, dispatch and receipts; in-scope refresh, expanded scope, repeated requests, reader-upgrade ordering and account-runtime layout.
- Existing G6, V3/V4 compatibility, package-installation, security, privacy, documentation and bilingual checks remain required.

## Complete package and local acceptance

Validate the declared source candidate with unchanged-worktree checks, payload, links, localization, semantics and all package/runtime tests. Historical copies in ignored directories are excluded from the formal source snapshot.

Local 7.16.2 acceptance verified installed files, Plugin registration and executing readers. One real human approval added 4 planning units, an actual Reviewer was created, its independent report and receipt gate passed, and the supplemental call settled exactly once. The original root-journal prefix stayed unchanged. Desktop was not restarted; native Hook execution was verified separately. Fixtures do not replace real human approval or an actual Agent call, and planning units do not represent actual charges.

## Evidence limits

Passing checks does not prove unexecuted scenarios. Reviewers were logical-readonly. The host terminal classification remains UNKNOWN, separately from the passing independent report. Some native source-write audit receipts did not complete during implementation; no substitute receipts were fabricated. Source, tests and artifacts were independently read back. Without current-chat native reservations and receipts, policy constraints are still not host enforcement. Only Codex Desktop is supported; package tests are not standalone CLI acceptance.
