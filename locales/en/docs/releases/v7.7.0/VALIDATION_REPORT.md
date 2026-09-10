# V7.7.0 Validation Record

Validation date: 2026-09-10. This record binds the final candidate; affected checks must rerun after any relevant change.

| Area | Current result and boundary |
|---|---|
| Operation v2 | Synthetic Git repositories cover A denial, preparation from an existing reference, atomic B claim, PostTool reconciliation, completion, and stale-evidence invalidation. Legacy GateTask never participates in a new permit. |
| Canonical patch adapter | Covers Add/Delete/Update/Move, multiple targets, UTF-8 byte budgets, path boundaries, links and parent changes, stale pre-state, and the 8 MiB per-target limit without persisting bodies. |
| Cancellation and failures | Cancellation before READY consumption is CANCELLED; cancellation after permission, policy changes, clock rollback, PostTool errors, and missing receipts converge to OUTCOME_UNKNOWN. |
| Compatibility evidence | Online verification passes 11/11: official async, Pre/Post schema, successful ApplyPatchToolOutput, PostTool payload, and string-response sources match frozen tags, commits, and SHA-256 digests. External report SHA-256: `b6663db0f194c8b58b698b05c95b7def2903bd22d73d39ee670a45dd77828591`. |
| Focused and full tests | Operation 16, Hook 19, and installer/compatibility 59 all pass. The final wrapper passes 327 package tests plus 179 runtime tests on Python 3.13.15. An earlier runtime pass skipped one unavailable symlink-creation probe; the wrapper summary is the final count. |
| Performance | Fifty real disabled/unconfigured file-gate processes measured p50 82.15 ms, p95 92.05 ms, and p99/max 269.76 ms. The enforcing path remains bounded by Git/hash work and the host's five-second timeout. |
| Uncovered scope | Hook permission cannot be atomic with tool side effects. Shell/MCP/unknown writers, account installation, Desktop restart, and original-project behavior require separate validation. |

Local implementation, tests, online source verification, and round-two logical read-only review are closed. Commit, push, tag, public assets, account installation, restart, and effective state still require separate post-action readback.
