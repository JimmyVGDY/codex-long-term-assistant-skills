# V7.8.0 Validation Record

This record reports source-candidate, public-release, and active-account effectiveness separately. Final counts are read back only after the release commit stabilizes.

| Boundary | Contract |
|---|---|
| C01-C25 | The static registry contains exactly 25 entries. An unclassified Manifest, Hook, or CLI entry blocks the all-covered claim without blocking ordinary conversation. |
| AUTO and authority | OFF, maximum, prerequisites, and risk are computed independently; `authorization=false` and `action_status=NOT_AUTHORIZED` are fixed. |
| First use | Only readback-confirmed `ACCEPTED_PERSISTED` can queue a full scan; no reply, decline, or write failure keeps BASIC available. |
| Scan jobs | Offer -> scan -> index lock order, lease generation, cancel epoch, index commit before cursor, late fencing, and three-attempt takeover ceiling. |
| Installation and recovery | Actual Python 3.11+ probes, feature doctor, read-only inventory, canonical recover, zero-delete state-less preview, and non-Git BASIC guidance. |
| Review | U02-U13, UX01-UX40, M01-M12, and T25-T28 have exact contracts and discoverable tests; postimplementation review is separate evidence. |

## Local candidate evidence

- `python scripts/validate-package.py`: PASS, 419 package + 205 runtime tests on Python 3.13.15.
- Focused results: capability registry 10, onboarding 15, scoped review 4, installer UX 12, installer security 40, and R3 traceability 76, all PASS.
- Windows lock-file concurrent initialization passed 30 consecutive stress iterations. Documentation, localization, links, semantic, privacy, routing, delegation, and payload gates passed.
- Fifty real disabled/unconfigured file-gate processes measured p50 82.22 ms, p95 87.35 ms, and p99/max 88.46 ms, within the p95 <= 300 ms and p99 <= 1 s budgets.
- Postimplementation state/concurrency and test/delivery Reviewers passed refreshed packet `f22009...a01402`. The decline-cancel compensation and false C20 entrypoint HIGH findings were repaired, with no unresolved blocker.
- Public CI, Release, anonymous download, account installation, restart, and fresh-task loading are not yet established by this record.

## Separate statuses

- `RELEASE_COMPLETE` requires commit, PR merge, tag, release workflow, public assets, anonymous downloads, and isolated installation readback.
- `INCIDENT_EFFECTIVE` requires active-account installation, any necessary restart, fresh-task loading, and original-project message acceptance. It is confirmed separately from `RELEASE_COMPLETE`.
- This file enters source as a candidate record; no project may claim either state without subsequent evidence.
