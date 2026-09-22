<!-- Generated from locales/en/docs/releases/v7.12.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.12.0 Validation Report

## Executed local validation

- Windows / Python 3.12.14 executed 617 package tests: 616 passed and one platform-conditional test skipped. All 231 runtime tests passed. The corresponding remote platform matrix must cover the skipped case.
- F01 completed 50 targeted regressions for named-root overlap rejection, authenticated recovery receipts, tampering rejection and keyless-diagnostic isolation. The repaired duplicate-concurrency scenario passed 16 consecutive runs. Prior failures remain recorded; assertions were not removed or timeouts merely relaxed.
- Exact new-feature test identifiers now participate in capability mapping. Every added required ID was executed successfully in the full run above; all 19 groups passed reprojection, followed by nine focused evidence tests after the mapping change. Reprojection is not another full test execution.
- F03 retains complete-history validation for every append and reuses only same-execution identity reads; 20 samples each at 100, 1,000, and 10,000 scale were executed. This does not claim improved asymptotic complexity.
- F04 passed 50 targeted checks. In 20 paired, same-account concurrent native samples on the current installed host, full status had a 2924.6905 ms median and 3521.541 ms p95; quick status had a 110.248 ms median and 115.587 ms p95, a local 96.23% reduction. Quick status is not complete validation or authorization and the measurement does not generalize to other environments.
- F05 had 52 passing cases. Its 16 native-host cases produced 8 PASS and 8 FAILED, so host acceptance is not passed: seven failures mix external `powershell-safe-invocation` into the plugin set, and one Chinese phase identifier does not match implement/review. Runner-contract diagnosis remains in progress.
- Documentation consistency, strict localization, internal links, privacy boundaries, semantic checks and a strict documentation-site build passed. F03 retains full-history validation on every append and combines only same-event repository identity reads; scale measurements do not establish a faster history-validation algorithm.

## Independent review and evidence scope

Two logical-readonly review rounds confirmed repairs for root-role collisions, authenticated recovery and release-digest drift, with no remaining confirmed code blockers. This report reflects executed facts; later document edits still require their own consistency/build checks.

The full execution applies to an uncommitted integrated candidate based on `6641ed24626925b3445a88014621ed530f8c2ee8`; its report digest is in the adjacent PACKAGE_VALIDATION.json. The eventual release commit still needs its own CI and build provenance; old candidate results do not validate a different commit.

## Remaining delivery evidence

- F02 completed three-scenario evaluation. The simple tool median changed from 6 to 5 (-16.7%, below the suggested 20% target), duration did not improve, and resume baseline passed 5/5 while candidate passed 4/5. The candidate shortcut is not delivered and the original LIGHT rule is restored. This does not attribute quality loss or failure to the rule and does not support general, stable, or causal efficiency claims.
- Documentation changes require rebuilding the previously reproducible bilingual ZIP candidates. Native-host failure repair and rerun, the complete remote matrix, final-commit CI, public Release, and account-external installation each require separate readback.

`RELEASE_COMPLETE` and `INCIDENT_EFFECTIVE` are evaluated separately. At this record's build time they are `RELEASE_COMPLETE=false` and `INCIDENT_EFFECTIVE=UNVERIFIED`; this does not establish effectiveness in already-open tasks or other business environments. Later public-release and installation results belong in a separate delivery record, without rewriting published tags or artifacts.
