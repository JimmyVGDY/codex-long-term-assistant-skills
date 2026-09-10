# Project capability index

The capability index stores locations and verification clues for reusable project entry points. Source, configuration, and tests remain authoritative. Index records grant no execution permissions and are never automatically promoted to stable project memory.

## Implemented scope

`runtime/cp_runtime/capability_store.py` provides storage APIs; `capability_index.py` provides bounded discovery, query-time verification, registration/migration, invalidation, and lifecycle updates; `capability_cli.py` integrates these operations into the existing runtime. Independent behavioral acceptance, cost comparisons, and installed-plugin loading still require separate evidence.

`CapabilityStore(profile_path, repo_path, index_root=None)` validates the existing Project Profile and State. An explicit index directory must be absolute and outside the repository. The default is `capability-index/<worktree_id>` beside the Profile. The worktree ID is the full SHA-256 of its normalized canonical root; each worktree needs its own matching Profile.

## Record contract

Schema 1 contains `schema_version`, `revision`, `identity`, `baseline`, `coverage`, `entries`, `recovery_source`, and `integrity`. Unknown and duplicate fields are rejected. Identity binds the project ID, repository fingerprint, Profile path and binding, worktree root and ID, and index directory.

The baseline contains HEAD, branch, and full hashes of explicitly observed files. Coverage records scopes, completion, pending paths, and enumerated limitations. Empty indexes are `UNSCANNED`. Entries hold stable IDs, locations, bounded summaries, references, verification scope, and their own `observed_baseline` and `observed_at`. Manual verification statements have a separate `recorded_at`. Lifecycle (`candidate`, `active`, `deprecated`, `removed`) is separate from freshness (`matched`, `recheck`, `stale`, `unknown`). File matching never proves business suitability.

Limits are 8 MiB and 2,000 entries per index, 500 characters per summary, and five references per category. Each scan enumerates at most 2,000 directory entries, performs at most 128 body reads totaling 2 MiB, and reads at most 128 KiB per file. Body budgets include final full-content verification, normally permitting at most 64 distinct initial reads. Context existence checks are cached and separately bounded, including final absence verification. Paths reject links, Windows reparse points/junctions, traversal, drive prefixes, control characters, and secret locations. Sensitive patterns supplement data minimization; they cannot detect every encoded secret.

## Commit and recovery

- Initialize with `commit(payload, expected_revision=None)` only when both snapshots are absent; the initial revision is zero.
- Updates require an exact revision. Under the existing process-owned lock, revalidate identity and read the current record. Identical facts produce no writes or revision changes.
- Validate the candidate, atomically publish the old current bytes to `index.previous.json`, verify them, then publish and verify `index.json`.
- A current-publication or subsequent verification failure reports `COMMIT_UNCERTAIN`. Read actual state before retrying; do not claim automatic rollback.
- `recover(expected_current_sha256)` uses the raw current-file hash, or `MISSING`, as a compare-and-swap condition. Validate the previous snapshot's format, identity, integrity, and revision order. Preserve existing raw bytes in `index.recovery-<sha256>.bin` in the same controlled directory, never in ordinary logs.
- Restoration keeps the previous snapshot and advances the revision to at least its revision plus two. An old recovery token conflicts; after rereading, unchanged recovery facts are a no-op. A current record with a foreign identity or unknown format is rejected rather than overwritten through recovery.

The protocol covers cooperating local tools under the same account, not privileged adversaries. Atomic publication protects each file individually; the two snapshots are not a database transaction. Valid on-disk snapshots and explicit readback determine recovery after process termination.

## Discovery and development commands

Use `python scripts/cp-runtime.py` in the source tree, or the verified installed runtime entry point. Every command requires `--profile` and `--repo-path`, with an optional absolute `--index-root`.

| Command | Purpose and parameters |
|---|---|
| capability-init | Create an explicitly unscanned index; reject existing snapshots |
| capability-scan | Repeat `--scope` for files/directories; default to bounded root discovery; use `--resume` for saved pending paths |
| capability-query | Search locations, symbols, registered responsibilities, and keywords using `--term`; default five candidates, `--limit` at most 20; `--include-inactive` includes deprecated/removed entries |
| capability-invalidate | Repeat `--changed-path`; mark related entries for review using references and module boundaries, expanding conservatively when dependencies are unknown; requires `--expected-revision` |
| capability-register | Read a complete validated entry from `--entry`; requires `--expected-revision`; the same ID at a new location is an explicit migration mapping, with source and references reread |
| capability-lifecycle | Explicit `--entry-id`, `--lifecycle`, and `--reason`; requires `--expected-revision`; reject removal while the file exists |
| capability-validate | Validate format, identity, and integrity with a bounded summary; a missing snapshot reports INDEX_MISSING; never create an index or approve semantic reuse |
| capability-recover | Restore explicitly using `--expected-current-sha256` |

Python AST discovery covers public top-level definitions and static `__all__` declarations. JavaScript/TypeScript text discovery covers common ESM and CommonJS export patterns; these remain candidates, not a complete parser or dependency graph. Dynamic exports, other languages, and unreadable contents retain limitations and can be registered explicitly after source verification.

Automatic discovery never copies comments, docstrings, or configuration values into summaries. It skips common dependency, build, and generated directories and never executes project code. Safe user-specified paths may remain in declared scopes; sensitive body content, derived summaries, and new body hashes are not persisted when scanning is rejected for sensitivity.

Body-budget exhaustion saves a bounded `coverage.cursor.pending` list; command output reports only its count. Continuation checks the Git baseline. An oversized directory records `DIRECTORY_BUDGET`: discovered pending paths can continue, but unseen directory tails need a narrower explicit scope. Repeatedly enumerating the same prefix cannot be reported as complete continuation. Completion only covers declared scopes and recognition strategies, never all project capabilities.

Queries reread candidate files, registered references, and nearby build configuration without writing the index. Changed source/configuration returns stale/recheck reasons. Missing indexes, no matches, and incomplete coverage require source search. Every query returns `semantic_reuse_approved=false`.

For a missing index, `maintenance` identifies a bounded initial scan for authorized first onboarding of nontrivial or shared-interface changes; source search remains available when that trigger does not apply. Invalidation returns `INVALIDATED_NOT_UPDATED` and the next bounded scan operation. These hints neither execute commands nor grant authorization.

After changed-source scanning, matched means current source, registered caller/test references, and build context match; it does not approve business suitability. Changes to source, context, or references clear old semantic verification evidence. Unmatched caller/test references remain recheck. Repeating a scan with unchanged facts does not increment revision merely to switch freshness.

Snapshot reading, explicit registration, and recovery-header parsing consistently reject duplicate JSON fields; recovery also rejects boolean schema versions. These rejections do not change either snapshot or create recovery archives. Valid recovery of explicitly identified damaged data retains the documented protocol.

After development, invalidate explicitly changed paths, then scan inspected changed sources plus stale candidate sources actually checked and adopted after querying. Refresh the latter even when their source was not edited. Unrelated unused entries may remain pending; updating fingerprints never approves business suitability. Use registration for semantic statements and explicit migration mappings. Each entry retains its own branch observation, preventing repeated scans after a branch switch from deleting another branch's capability. Unchanged scans, registrations, and invalidations do not repeatedly increase revisions.

When a declaration changes at the same file/symbol locator, rescanning refreshes its function/class/component/module kind and invalidates prior semantic evidence while preserving its ID, manual summary, boundaries, and references. Explicit service/adapter kinds describe business roles and are not overwritten by syntax classification; source changes still invalidate their prior verification.

To rebuild a corrupt index without a valid previous snapshot, scan authorized scopes into a new explicit external directory, verify it, preserve the old directory, and record the new location in the external task handoff. Do not silently change the Profile or remove old state.

## Targeted validation

Projects use `capability-gate-enable/status/disable` to manage an explicit project policy. The gate defaults off and leaves ordinary conversations and unconfigured projects unchanged. V7.7.0 routes the canonical `apply_patch` path through repository-external Operation v2: A creates an origin and is denied, `capability-task-prepare --operation-ref ... --term ...` only consumes that origin, a new B atomically claims READY before writing, and only its real PostToolUse receipt can proceed to `finish/check`. The CLI creates neither origins nor dispatch IDs. Legacy GateTask, PREPARED/PASS, and old receipts never become v2 permits. Missing receipts, policy changes, cancellation after permission, and stale evidence remain `OUTCOME_UNKNOWN`. Edit/Write are matcher aliases only; shell, MCP, and other uncovered writers cannot be reported as protected. Source implementation, package validation, installed loading, and fresh-task acceptance remain separate evidence layers.

```text
python -m unittest discover -s runtime/tests -p "test_capability*.py" -v
```

Tests cover identity, idempotency, revision conflicts, real subprocess competition, killed lock owners, publication faults, explicit recovery, size limits, sensitive fields, read races, and Windows junctions. Junction coverage is explicitly skipped outside Windows. These checks do not replace discovery, semantic, cost, or installation acceptance.

Default traversal skips `.agents` and `.codex` tooling directories to avoid treating assistant tools as business capabilities. Explicit source-file scopes remain available when maintaining those tools themselves.

Normally omit `--index-root`. The reserved `<Profile directory>/capability-index` container cannot be used as a snapshot directory: misuse returns `INDEX_ROOT_IS_CONTAINER_OMIT_OVERRIDE` without writing. Explicit worktree snapshot directories and other authorized custom directories remain supported.

The cold-index scan exception is limited to one existing file. Multiple or new prepared files require bounded scanning; every previously prepared file must remain unchanged before an exception expands. Current checks invalidate nonqualifying legacy no-index PASS receipts as BLOCKED with INITIAL_SCAN_NOT_PROVEN, while valid single-file receipts remain usable. This predicate does not approve single-file business semantics; projects without the gate retain their behavior.

Related: [Capability index](CAPABILITY_INDEX.md) · [Acceptance protocol](COMPONENT_REUSE_ACCEPTANCE.md) · [V7.7.0 validation](releases/v7.7.0/VALIDATION_REPORT.md).
