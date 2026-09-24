<!-- Generated from locales/en/docs/releases/v7.13.3/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.3 Validation Record

This is a pre-publication source record. Subsequent full checks, artifacts, installation, and public release are established by their corresponding commits and action readbacks.

| Area | Evidence and limits |
|---|---|
| Windows path regressions | Eighteen tests passed for the final eight-file fix, covering alias lookup, old fingerprints, conflicts, concurrent binding, explicit ledgers, lifecycle proof, unavailable identity, root protection, and missing child targets. |
| Existing V4 routing | 111 tests passed after atomic proof corrections. The later missing-child adjustment is covered by the final eighteen tests. |
| Earlier runtime checks | An earlier revision ran 231 tests: 228 passed and three skipped. This does not replace final-version full validation. |
| Existing ledger preservation | Source-only readback resolved both spellings to the same existing ledger with identical before/after bytes. This is not native callback evidence. |
| Independent targeted inspection | A separate Desktop task checked fixed hashes for all eight files and confirmed the reported issues resolved. This was logical read-only inspection, without a system-isolation or full-release review claim. |
| Release acceptance | Full post-version-sync checks, cross-platform matrices, reproducible artifacts, installation, and public release require separate readbacks. |
| Native admission and model qualification | Not accepted. GPT-6 production defaults remain disabled; source and synthetic checks do not establish enforced budgets. |

Historical policies, ledger formats, and evaluation gates are unchanged. Unavailable filesystem identity rejects the operation; prior failures, unknown consumption, and unsuccessful acceptance records remain preserved.
