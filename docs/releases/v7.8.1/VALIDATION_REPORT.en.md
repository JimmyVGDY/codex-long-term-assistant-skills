<!-- Generated from locales/en/docs/releases/v7.8.1/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.8.1 Validation Record

This record reports source-candidate, public-release, and active-account effectiveness separately. Final counts are read back only after the release commit stabilizes.

| Boundary | Contract |
|---|---|
| C01-C25 | The static registry contains exactly 25 entries. An unclassified Manifest, Hook, or CLI entry blocks the all-covered claim without blocking ordinary conversation. |
| AUTO and authority | OFF, maximum, prerequisites, and risk are computed independently; `authorization=false` and `action_status=NOT_AUTHORIZED` are fixed. |
| First use | Only readback-confirmed `ACCEPTED_PERSISTED` can queue a full scan; no reply, decline, or write failure keeps BASIC available. |
| Scan jobs | Offer -> scan -> index lock order, lease generation, cancel epoch, index commit before cursor, late fencing, and three-attempt takeover ceiling. |
| Installation and recovery | Actual Python 3.11+ probes, feature doctor, read-only inventory, canonical recover, zero-delete state-less preview, and non-Git BASIC guidance. |
| AGENTS ownership | Verify only the unique managed block. User text outside markers is not drift, while block changes, duplicates, missing markers, and path escapes remain fail closed. |
| Review | U02-U13, UX01-UX40, M01-M12, and T25-T28 have exact contracts and discoverable tests; postimplementation review is separate evidence. |

## V7.8.1 patch candidate evidence

- Public V7.8.0 installation reproduced the issue: verify, doctor, and Plugin readback passed, but old inventory reported only AGENTS as `DRIFT`; the reconstructed managed-block digest exactly matched the source block.
- After repair, five focused regressions passed and the active V7.8.0 state read back as 13/13 `MANAGED` through the new inventory. A new test covers user edits outside markers remaining managed and managed-content edits becoming `DRIFT`.
- A full `python scripts/validate-package.py` rerun passed 423 package + 205 runtime tests on Python 3.13.15. Documentation, localization, links, semantic, privacy, routing, delegation, payload, and worktree-side-effect gates all passed.
- Windows lock-file concurrent initialization passed 30 consecutive stress iterations. Documentation, localization, links, semantic, privacy, routing, delegation, and payload gates passed.
- Fifty real disabled/unconfigured file-gate processes measured p50 82.22 ms, p95 87.35 ms, and p99/max 88.46 ms, within the p95 <= 300 ms and p99 <= 1 s budgets.
- R3 postimplementation state/concurrency and test/delivery Reviewers passed premerge refreshed packet `f22009...a01402`. The decline-cancel compensation and false C20 entrypoint HIGH findings were repaired. V7.7.1 compatibility changes have their own independent review and release evidence. The combined baseline received the full local rerun above and is not represented as a new independent Reviewer pass.
- V7.8.1 is a single-point installation-evidence projection patch with focused and full local reruns. The V7.8.0 independent Reviewer result is not represented as a new independent patch review.
- Public CI, Release, anonymous download, account installation, restart, and fresh-task loading are not yet established by this record.

## Separate statuses

- `RELEASE_COMPLETE` requires commit, PR merge, tag, release workflow, public assets, anonymous downloads, and isolated installation readback.
- `INCIDENT_EFFECTIVE` requires active-account installation, any necessary restart, fresh-task loading, and original-project message acceptance. It is confirmed separately from `RELEASE_COMPLETE`.
- This file enters source as a candidate record; no project may claim either state without subsequent evidence.
