<!-- Generated from locales/en/docs/releases/v7.17.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.17.0 Validation Report

The functional baseline is official v7.16.2 (`2604e8b`); the release tag points to `bddff85`. [V7.17.0](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.17.0) became public at 2026-10-16 20:23:25 UTC. The [release workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38949645896), pre-merge CI and post-merge CI passed, and [PR #26](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/pull/26) merged. This report separates publication readback, bounded synthetic acceptance, historical failures and unknowns.

## Publication readback

| Platform / Python | Package cases | Runtime cases |
|---|---|---|
| Windows / 3.11 | 1357 passed, 2 skipped | 265 passed |
| Windows / 3.13 | 1358 passed, 1 skipped | 265 passed |
| Linux / 3.11 | 1315 passed, 44 skipped | 259 passed, 6 skipped |
| Linux / 3.13 | 1315 passed, 44 skipped | 259 passed, 6 skipped |

Each combination discovered 1359 package cases and 265 runtime cases. Skip reasons are retained separately and are not counted as passes. All four reports bind to the tagged commit; build, attestation and draft re-verification succeeded.

All six public assets were downloaded anonymously and matched the immutable CI candidate byte for byte. Checksums, reproducibility witnesses and both archive checks passed; each archive contains 943 entries. The Chinese archive SHA-256 is `a30a318908a75912b94caf9536b80dbe3bc43d81a64082930f896c093abd6166`; the English archive is `b182454869baeeb603e8f1ff658b5d7525165f1ab69e547192ccb669eac8d32a`. The release workflow signed the provenance and verified both archives with `gh attestation verify` before creating the draft. Local downloads are bound to that candidate digest.

The official Chinese package's 350-file payload matches the existing managed installation source, and installation verification passed. Native subtask calls after installation were recorded; the claim covers those calls only. Desktop was not restarted, and this does not establish complete activation in a new chat or across every capability.

## Six-track acceptance

| Track | Observed evidence | Limits |
|---|---|---|
| W01 artifact comparison | One independent baseline/candidate pair for an existing reuse case; hidden assertions and protected-input checks passed | One pair does not establish general benefit |
| W02 independent readers | Five pairs and ten answers across installation, recovery and architecture documents; factual and protection checks passed; recovery repeated three times per version | Installation/recovery used Sol/medium and architecture used Luna/medium, matching within each pair; no cross-model benefit aggregation |
| W03 frontend design | Five pairs, ten pages and twenty target-size screenshots across a public page, administration form and local design-system extension; latest valid browser reports contain 406 passing assertions; extension repeated three times per version | Original-image digests rechecked; an independent agent viewed all twenty originals, with ties allowed and no general visual-benefit claim; report protocol limits appear below |
| W04 routing evaluation | Eighty independent executions across 24 intent cases; baseline: 27 passing and nine failing among 36 valid reports; candidate: 29 passing and eight failing among 37 valid reports; six invalid reports and one host-blocked trial retained | Both development and final evaluation remain FAILED; expectations and answers were not rewritten, and missing evidence is not success |
| W05 browser acceptance | Fourteen Windows synthetic-service/browser checks passed and owned-resource cleanup was verified | The preexisting-service case is synthetic, not production-backend proof |
| W06 MCP acceptance | Ten answers across six synthetic task families passed answer and protection checks; pagination and permission cases each repeated three times; native JSON-RPC evidence inspected | Redundant first-page fetches, corrected client errors and one coordinator cleanup of owned processes remain recorded; no complete protocol-conformance or real-connector claim |

W04 used Luna/low and frozen rule snapshots. Its evidence level is `host_final_report`, not independently signed loader traces or proof that historical packages were installed. Native task-name hints were added from row 20, without expected Skill choices. Real gate failures were repaired during execution while prompts, catalogs and scoring stayed frozen. Repeats are not new intent families. Trigger descriptions were not changed; general benefit remains UNKNOWN. The enhanced evaluation capability ships while existing descriptions remain.

## Gates, regressions and installation

- A native external-artifact request was registered, written and read back. The coordinator registered precise child scopes after verifying direct human authorization, parent/child identity and target paths. Host filesystem permissions were unchanged.
- Continue registration retained the original task ledger. A later human correction can restore the same allowance request while preserving the refusal, limits and all usage. Equal timestamps are ordered by native-record byte positions.
- A real batch of eleven parallel reads hit `G6_CONTEXT_LOCK_BUSY`. The same 626-event journal snapshot reproduced nine successes and two timeouts. Moving complete snapshot replay outside the read lock gave eleven first-attempt successes; thirteen budget and sixty-six related regressions passed. Writers still revalidate under lock; complete hash-chain, identity and budget checks remain.
- All four Windows/Linux and Python 3.11/3.13 CI jobs for `ca62f3f` succeeded after one bounded retry. The first Windows 3.13 package run timed out at 3600 seconds and remains preserved with unknown root cause. CI tested merge snapshot `898d808`, with no file differences from `ca62f3f`; this does not substitute for the later `812e408` matrix.
- Both Windows package jobs for `812e408` timed out at 3600 seconds; each runtime suite passed 265 tests. For `9d8e5d3`, Windows 3.13 completed successfully, Windows 3.11 package tests timed out, and Linux passed. Original failures remain. The package-only limit was then set to 5400 seconds while other commands/runtime retain 3600; thirteen affected regressions and nine boundary probes passed, followed by the complete release matrix. An extra local timing diagnostic was stopped because its wrapper lacked a Windows multiprocessing entry guard; it is not correctness or reliable timing evidence.
- Candidate 13 came from clean `9d8e5d3`, with reproducible, verified bilingual ZIPs containing 943 entries each; only documentation differs from candidate 12. Candidate 12 also produced reproducible, verified bilingual ZIPs with 943 entries each. The 350-file Chinese payload digest is `485da8f8b2b479686818a02ab05cf9dcdddd44079be4a5ac2c06eb6803c29796`. Install-output capture failed decoding, so that command's exit status remains UNKNOWN. Subsequent installation verification passed and account/cache reader digests matched; no blind reinstall was attempted.
- Desktop was not restarted. Installation readback, specific native calls and complete current-chat activation are separate evidence levels. Missing comprehensive host proof is not relabeled PASS.

## Final independent review

Security and state/concurrency reviewers returned `nonblocking` and `pass`, respectively, with no actionable findings; their native reports and scope digests were verified. The delivery reviewer independently inspected all twenty original images across five pairs, corroborated by the native image-tool outputs. This is agent assessment, not human feedback.

The delivery report used `PARTIAL`, outside the G6 review status enum, so the controller did not accept it as machine-verified review success. Its original text, usage, visual judgments and format failure remain preserved, and the controller closed with unverified items. Its form-header finding was rejected after checking the initial-file digest: the N logo, styled white header and helper text came from the baseline-generated output, whereas the original form contained only the Northstar Admin identity. The stricter header/shell requirement belongs to a separate extension case. Frozen outputs were not rewritten to satisfy this false positive, and the same review was not dispatched again.

## Retained failures and unknowns

An earlier complete candidate package run executed 1325 tests: 1303 passed, nine failed, twelve errored and one skipped. Later targeted repairs do not rewrite that report. The `55aeb55` Windows 3.11 single-test error is also retained with unknown root cause. Raw artifacts, failed attempts and review material remain outside the repository.

Some expired or missing post-write finish receipts remain UNKNOWN; files, successful tool receipts and test results are verified separately. Actual charges, general benefit, review protocol verification limits and public-release readback remain distinct from planning units, unit tests and executor claims.
