# V7.12.0 Release Notes

V7.12.0 is a candidate for reliability, validation evidence, and day-to-day diagnostics improvements. It keeps Codex CLI `0.155.1` as the compatibility anchor and retains the eleven-release stable window. This record covers a local integrated candidate and local installation readback; commit, CI, artifacts, public publication, and effectiveness in already-open tasks remain separate gates.

## Candidate changes and executed evidence

- F01 adds phase-aware SessionEnd permission fallback. Fifty targeted regressions and 16 concurrent stress repetitions passed, including named-root overlap rejection, authenticated recovery receipts, tampering rejection, and keyless-diagnostic isolation.
- F02 completed three-scenario evaluation. The candidate shortcut is not delivered and the original LIGHT rule is restored. The simple tool median changed from 6 to 5 (-16.7%, below the suggested 20% target), duration did not improve, and resume baseline passed 5/5 while candidate passed 4/5. These results do not attribute quality loss or failure to the rule and do not support stable cost, general-efficiency, or causal claims.
- F03 retains complete-history validation for every append and reuses only same-execution identity reads. Twenty samples each at 100, 1,000, and 10,000 scale were executed; this is not a claim of improved asymptotic complexity.
- F04 adds explicit `status --quick` while default `status` keeps the complete check. Fifty targeted tests passed. In 20 paired, same-account concurrent native samples on the current installed host, full status had a 2924.6905 ms median and 3521.541 ms p95; quick status had a 110.248 ms median and 115.587 ms p95, a local 96.23% reduction. Quick status does not provide complete validation or authorization, and this result does not generalize to other accounts, hosts, or a public release.
- F05 adds positive/negative controlled-evolution governance and phase-routing regression coverage. Fifty-two cases passed, but the 16 native-host cases produced 8 PASS and 8 FAILED, so host acceptance is not passed: seven failures mix external `powershell-safe-invocation` into the plugin set, and one Chinese phase identifier does not match implement/review. Runner-contract diagnosis remains in progress.
- F06 binds complete-validator capability conclusions to discovered and executed unittest identifiers and results. Missing, all-skipped, failed, errored, subtest-failed, unexpected-success, timed-out, or corrupted evidence never projects to `PASS`. Nineteen capability groups passed reprojection after the complete run, followed by nine focused evidence tests.

## Evidence boundary and remaining items

- Local complete validation ran 617 package tests: 616 passed and one platform-conditional test skipped; all 231 runtime tests passed. These results apply to the uncommitted integrated candidate based on `6641ed24626925b3445a88014621ed530f8c2ee8`, not to a future commit's CI or artifact provenance.
- The final payload was regenerated and installed with a managed backup. Independent status readback confirms installed, enabled and compatible; source, marketplace and cache share the same 245-file digest `b8c7d0c24f1a044a58f25c3324143e51ec5e634e9857c6f571dbef87e6f77450`. This does not replace fresh-task routing, final-commit CI or public-release acceptance.
- In F02 ordinary samples, baseline had three PASS and two timeout `UNKNOWN` results; candidate had five PASS results. Successful tool counts were baseline `[8,13,11]` and candidate `[7,13,10,7,7]`. Original resume samples were 0/5 on both sides because synthetic external-context reads were denied; those failures remain and a parent-workspace read-only rerun is in progress.
- Two bilingual ZIP candidate builds were reproducible, but documentation changes require rebuilding them; the old ZIP is not a final public asset. The final commit, remote matrix, native-host failure repair and rerun, CI, tag, and GitHub Release each require separate confirmation.

Upgrades support V7.11.2 and the older versions declared by the manifest. Commit, tag, public release, installed state, and effectiveness require separate readback.
