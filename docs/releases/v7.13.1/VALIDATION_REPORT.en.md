<!-- Generated from locales/en/docs/releases/v7.13.1/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.1 Validation Record

This is a pre-publication source record, not a declaration that the full objective is complete. Compatibility support retains frozen V3; native dispatch, model qualification, and production-default activation require separate acceptance.

| Area | Current evidence |
|---|---|
| Backup preservation | Corrupt/missing backup regressions first failed, then passed. Six targeted tests passed, including interrupted recovery, external drift, old-transaction rejection, and ownership protection. |
| Subtest exception classification | The new regression first failed, then passed. Twelve report tests passed, covering legacy reports, allowlisting, fail-closed outcomes, and private-body exclusion. |
| Test limits | The installer test-process deadline is now 120 seconds, preventing the former 30-second outer wait from preempting the host's 60-second per-command limit. Functional assertions, production command limits, and Hook deadlines are unchanged. |
| Full patch validation and artifacts | The complete post-version-sync matrix, reproducible bilingual archives, and provenance remain pending. Targeted results do not replace full validation. |
| Installation and real execution | Installation of the preceding compatibility candidate was verified; this patch's installation and native dispatch require separate readback. |
| Model qualification and gains | Production qualification has not been established. Synthetic tests and successful installation do not establish model quality, reasoning gains, or enforced budgets. |

The intermittent Windows subtest failure in the V7.13.0 release workflow remains unexplained. Original-order and formal-prelude diagnostic runs passed, which does not prove that the original issue is fixed. The improved classification preserves exception types for future formal validation; all prior failures remain recorded.

The first V7.13.1 Windows 3.11 check recorded `TimeoutExpired` in one installer case while the other three operating-system/interpreter combinations passed. This exception originated from the test wrapper's 30-second wait. Changing that deadline does not convert a failed result into a pass; complete checks must run again. Seven local PowerShell-entry failures separately came from the default script execution policy and passed under `RemoteSigned` in a dedicated validation process; persistent account-level and system policies were unchanged.

Public release still requires commit, tag, asset, provenance, documentation-site, and installation readback. This source record cannot substitute for those external facts.
