<!-- Generated from locales/en/docs/releases/v7.11.0/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.11.0 Audit Report

This correction assigns a distinct version to the new review capabilities previously installed under 7.10.0. Historical 7.10.0 release evidence retains its original bytes. V7.11.0 uses its own manifests, compatibility digest, artifact names, and installation cache directory.

Earlier independent reviews closed the lifecycle-receipt bypass and implicit-permit-matching findings. This version update changes none of their algorithms, scoring weights, or authority boundaries.

The version-correction stage covered local edits, builds, verification, and account upgrade. A subsequent cross-device handoff separately authorizes commit and push to the feature branch, without publication or workflow execution. Installation retains transaction backups; existing task context is not hot-reloaded.

## Continue on another device

Preserved branch: `codex/reviewer-model-routing-v2`. The package identifies as 7.11.0, with account installation and fresh CLI loading verified on the original device. Those records do not establish installation acceptance on another device. This snapshot preserves progress; it is not a release-ready conclusion.

The current `luna-evidence-v1` scoring formula has a reproduced, unresolved issue: selecting one item per root cause before applying dimension caps can reduce the score when a valid classification is added.

| Synthetic input | Result |
|---|---|
| Root A semantic multi-domain evidence worth 8, independent root B concurrency evidence worth 8, and economy base 1 | 17 units, Sol Medium |
| Retain both items and add a concurrency classification worth 8 for root A | 9 units, Terra High |

The fixed tie priority makes A's concurrency classification displace its semantic classification. The dimension cap then retains only one concurrency item. The original A-semantic plus B-concurrency combination remains valid. This counterexample exercises only the scoring function; it makes no model call or Reviewer dispatch.

Resume by reading the [scoring implementation](../../../runtime/cp_runtime/dispatch_policy.py), [policy parameters](../../../runtime/cp_runtime/data/dispatch-policy-v2.json), and [existing property tests](../../../tests/test_dispatch_policy.py). After an explicit continuation instruction:

1. Select the best scoring combination jointly under one-per-root and one-per-dimension constraints. Cover additions that neither invalidate old evidence nor merge previously independent roots.
2. Reconsider quality constraints and budget selection instead of automatically choosing the highest affordable weight; the replacement selection rule is not finalized.
3. Distinguish missing material, tool failure, and reasoning limitations before awarding inconclusive-review points.
4. Introduce a new formula version for algorithm changes while preserving old ledger and scorecard replay. Never overwrite frozen policy semantics and pretend historical results are unchanged.

Current state: the scoring issue remains unfixed; optimization is analysis only. Stop after commit and push. Do not merge into the default branch, create version tags or Releases, or manually trigger GitHub Actions. Recheck project binding and host compatibility on the new device; do not reuse machine-specific absolute paths or treat earlier runtime evidence as new acceptance.
