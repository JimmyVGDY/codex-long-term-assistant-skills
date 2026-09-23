<!-- Generated from locales/en/docs/releases/v7.12.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.12.0 Validation Report

## Executed local validation

- Windows / Python 3.12.14 executed 617 package tests: 616 passed and one platform-conditional test skipped. All 231 runtime tests passed. The corresponding remote platform matrix must cover the skipped case.
- F01 completed 50 targeted regressions for named-root overlap rejection, authenticated recovery receipts, tampering rejection and keyless-diagnostic isolation. The repaired duplicate-concurrency scenario passed 16 consecutive runs. Prior failures remain recorded; assertions were not removed or timeouts merely relaxed.
- Exact new-feature test identifiers now participate in capability mapping. Every added required ID was executed successfully in the full run above; all 19 groups passed reprojection, followed by nine focused evidence tests after the mapping change. Reprojection is not another full test execution.
- F03 retains complete-history validation for every append and reuses only same-execution identity reads; 20 samples each at 100, 1,000, and 10,000 scale were executed. This does not claim improved asymptotic complexity.
- F04 passed 50 targeted checks. In 20 paired, same-account concurrent native samples from historical payload `948c`, full status had a 2924.6905 ms median and 3521.541 ms p95; quick status had a 110.248 ms median and 115.587 ms p95, a local 96.23% reduction. The current final payload has not been remeasured. Quick status is not complete validation or authorization and the measurement does not generalize to other environments.
- F05 had 52 passing cases. The original 16 independent host tasks had 13 PASS and three FAILED results, retained as history. The fixed profile, scorer and runner, plus SHA-256-bound unchanged evidence bytes for 13 original cases and three targeted follow-up tasks, produce `HOST_FINAL_REPORT` combined coverage: 16 actual independent tasks observed, 16 PASS and none missing. This does not claim a single-cohort pass rate or an independent router trace, and applies only to this profile.
- Documentation consistency, strict localization, internal links, privacy boundaries, semantic checks and a strict documentation-site build passed. F03 retains full-history validation on every append and combines only same-event repository identity reads; scale measurements do not establish a faster history-validation algorithm.

## F03/F04 controlled measurement supplement

| Area | Confirmed result | Boundary |
| --- | --- | --- |
| F03 controlled matrix | Five groups of 20 were all valid with zero failures: fresh-process without pre-read versus explicit pre-read; 1,286 records / 1,049,376 B active boundary; 20 non-rollovers at 2 MiB versus 20 rollovers at 1 MiB, all with complete verification; and 80 appends from 20 fixtures × four threads with count, IDs and head all valid. | The OS cache was not purged, so OS-cold behavior is unverified; no complexity improvement is claimed. |
| F04 component diagnostic | On the installed account at `306f3ed`, 20 pairs / 40 real in-process `status()` calls used thin wrappers and left all hashes unchanged. Full was semantic `PASS` for 20/20, with 2383.559 ms median and 2493.692 ms p95; quick exited 0 for 20/20 but semantic status is `NOT_EVALUATED`, with 4.788/5.475 ms median/p95. | This is not a CLI end-to-end measurement, cannot be compared directly with the historical 110.248 ms CLI result, and does not support a new release headline percentage. Instrumentation overhead was not separately calibrated. |

F04 full component medians were 2011.035 ms host, 107.783 ms source payload, 116.599 ms marketplace, 121.033 ms cache, 2.293 ms state initial, and 2.585 ms stability reread. Each payload read 1,740,070 B and state read 7,893 B. The host 341 B counts only parent-process wrapper reads, not all child-CLI I/O.

## Codex 0.156.0 and the installed sealing path

The existing current-plus-ten policy now anchors at `0.156.0`, with frozen npm digests, official source commits and interface evidence. Windows isolated installation/removal, CLI and synthetic Hook contracts pass; 39 targeted compatibility/release checks pass.

Real execution found that the account Hook sought `seal_worker.py` in a directory where it had never been installed. The installer now backs up, deploys, verifies and removes it as a managed component. The Hook invokes its sibling worker, and a missing entry fails before process creation. All 47 recovery/deferred-worker/installed-layout checks and 11 validation-evidence tests pass, including missing-file, tampering and removal checks. This delivery-path delta received scoped INLINE inspection; it is not presented as a new independent Reviewer result.

A fresh parent/child task completed on `0.156.0`. All five real lifecycle event types occur once and the five-record head is `SEALED_CURRENT`; all ten current Hook definitions are trusted. Installed payload `4d16bf233697500fd2f4087f356037dbe61aa93af61670b289b44cd0b1a0abc7` matches across source, marketplace and cache (245 files), with a retained backup.

This host's configured elevated sandbox fails while pinning a directory; a read-only reproduction of the official primitive returns `0xc000050b` / Windows `4395`. Acceptance uses the documented `unelevated` fallback and a read-only policy only for its processes; the global configuration digest is unchanged. This does not claim that elevated setup was repaired, or that other environments or already-open tasks are effective. See the [official Windows sandbox fallback guidance](https://learn.chatgpt.com/docs/config-file/config-basic#windows-sandbox-mode).

## Independent review and evidence scope

Two logical-readonly review rounds confirmed repairs for root-role collisions, authenticated recovery and release-digest drift, with no remaining confirmed code blockers. This report reflects executed facts; later document edits still require their own consistency/build checks.

The full execution applies to an uncommitted integrated candidate based on `6641ed24626925b3445a88014621ed530f8c2ee8`; its report digest is in the adjacent PACKAGE_VALIDATION.json. The Windows-Hook-fixed managed installation exited 0; the earlier candidate payload `be78741f82a310e5af03eeb1095799aff18be697c12c06c9d51f0ffa3e2ed0cb` has 245 matching files in repo, marketplace and cache, and supplemental host readback confirms installed and enabled. Later native results appear above; release-commit CI and build provenance remain separate evidence.

## Remaining delivery evidence

- F02 completed three-scenario evaluation. The simple tool median changed from 6 to 5 (-16.7%, below the suggested 20% target), duration did not improve, and resume baseline passed 5/5 while candidate passed 4/5. The candidate shortcut is not delivered and the original LIGHT rule is restored. This does not attribute quality loss or failure to the rule and does not support general, stable, or causal efficiency claims.
- Documentation changes require rebuilding the previously reproducible bilingual ZIP candidates. The complete remote matrix, final-commit CI, public Release, and account-external installation each require separate readback.
- Two Linux CI jobs for current `306f3ed` succeeded. Only the actual Ubuntu Python 3.13.15 report has the following counts: 626 package tests (608 PASS, 18 SKIP) and 231 runtime tests (225 PASS, 6 SKIP); they are not a combined count for both jobs. Its checkout was `3cc8d22c2a60df59112a5caef07f7ecfa97833e1` and tree `ef4fbf24383e7e5a1fab60faa42cd87366dbc810`, verified to match the CI tree for `306f3ed5ccf7d78cdce92e128c1ad849dfe30e64`. Windows checks on that historical source subsequently passed; this does not replace final-commit CI for the new window and worker fix. The five `test_event_scaling` IDs in the earlier 617-test evidence belong to the package suite, not runtime.

`RELEASE_COMPLETE` and `INCIDENT_EFFECTIVE` are evaluated separately. At this record's build time they are `RELEASE_COMPLETE=false` and `INCIDENT_EFFECTIVE=UNVERIFIED`; this does not establish effectiveness in already-open tasks or other business environments. Later public-release and installation results belong in a separate delivery record, without rewriting published tags or artifacts.

- New `0.156.0` host acceptance retains 13 original passing independent tasks and the host execution error that stopped that cohort. A targeted follow-up covers the interrupted case and two unstarted cases. Verified raw metadata, projections, report hashes and actual task IDs produce 13+3 combined coverage of the unchanged 16-case profile, all passing with no missing cases. Execution uses temporary `unelevated` plus read-only policy. Evidence remains `HOST_FINAL_REPORT`, not one-shot success or an independent router trace.
