# V7.6.0 Validation

Evidence is separated by layer. The pre-release implementation candidate passed canonical Linux package validation (284 package and 142 runtime tests). On this Windows account, two complete runs exceeded the existing 900-second runtime-group limit; two disjoint runtime batches passed. Those timeouts remain failures, not full Windows passes. Platform-specific skips are not counted as platform coverage.

The final natural-task cohort passed business and protected-input checks in 11 of 11 samples; workflow results were 10 PASS and one OUTSIDE_SCOPE block. A separate stale-index replay passed and does not replace the blocked sample. Two fresh tasks loaded the account-installed candidate through CLI and Desktop binaries, exercised initial scan and follow-up reuse, preserved capability IDs, and invalidated an old receipt after later edits. This proves bounded examples, not universal stable reuse or an already-open Desktop session hot reload.

An offline isolated source trial reused existing frontend, backend and provider interfaces; type checks, build, rendering and backend assertions passed. An oversized lockfile retained CONTEXT_UNCONFIRMED. No real business source was sent to a model for that trial. An earlier synthetic probe unexpectedly reached the model service; its exact payload remains UNKNOWN and the earlier zero-model-call claim was withdrawn.

Independent logical-read-only review findings were repaired. Later evidence reconciliation was performed by the primary coordinator and is not another independent review. No net token saving, P95 improvement or break-even point is established.

These observations precede the version metadata update. Final V7.6.0 package, Windows/Ubuntu compatibility, reproducible archives, account loading, public Release and Pages deployment must be read back on their exact commit/version. The [tag workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/release.yml), [public release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.6.0) and its six verified assets provide publication evidence; this document does not predeclare those operations successful.

[Release notes](RELEASE_NOTES.en.md) · [Audit](AUDIT_REPORT.en.md) · [Acceptance protocol](../../COMPONENT_REUSE_ACCEPTANCE.en.md).

The V7.6.0 candidate subsequently passed canonical Linux validation: 284 package tests and 142 runtime tests, with unchanged source and snapshot hashes during the run. The generated [package report](PACKAGE_VALIDATION.json) replaces the explicit PENDING bootstrap record. Subsequent changes are documentation corrections and preservation of existing registry line endings; final commit CI independently validates the published tree.
