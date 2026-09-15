<!-- Generated from locales/en/docs/releases/v7.10.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.10.0 Validation Report

This report records local evidence for the 7.10.0 repair candidate on 2026-09-15. Completion requires CI for the target commit, the public Release, download verification, and the external delivery record. This file alone proves neither publication nor effectiveness in the current account.

Focused checks passed: 41 status/diagnostic tests, 8 benchmark-tool tests, and 25 recovery/process-resource tests (2 skipped because Windows link privileges were unavailable). Recovery coverage includes complete snapshots matching the legacy algorithm, STALE after source changes, unused text converters, refusing applicable converters without executing them, aggregate read budgets, identity conflicts, and file-byte invariance. Diagnostic coverage includes healthy base-only installation, disabled/unknown/duplicate registration, required-control failures, transaction priority, changing samples, and bounded journal reads.

The preceding full run reached 228 runtime tests and found 2 recovery failures: a configured converter unrelated to the changed files incorrectly made the snapshot incomplete. The issue is fixed and the focused regressions above pass; full package validation must run again. Pre-repair package, archive, and validation digests must not stand in for this candidate.

Bilingual source/projection checks, strict localization audit, and 1,123 repository-internal link checks passed. Navigation now consistently names V7.10. Final site construction and remote Pages still require binding to the final commit.

Independent review was logically read-only. The three findings concerning transaction-action priority, changing read errors, and nonexistent benchmark input were repaired together and covered by focused counterexamples. Final-diff binding, repair records, and review closeout are maintained outside the repository and must complete before publication.

Isolated native Codex 0.154.0 passed authentication, ten-Skill discovery, and real model/terminal-tool preflight. The private harness uses in-memory token authentication through the native app-server without copying or persisting credentials; this is not a new product interface promised across hosts. Three samples per version for each real-task scenario, twenty paired wrapper measurements, the final ZIP installation matrix, and pre-publication native acceptance have separate records. Failed, timed-out, and unknown observations remain visible. Process exit is not an external oracle, and small samples do not prove general speed improvements.

Upgrading the actual account and restarting Desktop are outside this execution scope. Installed files, Plugin registration, fresh CLI loading, task behavior, the current Desktop session, and business-project effectiveness require separate evidence.
