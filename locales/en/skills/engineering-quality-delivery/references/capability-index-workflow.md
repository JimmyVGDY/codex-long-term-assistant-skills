# Capability Index in Development

The index is a project-isolated locator of observed facts. Source, contracts, and consumers determine suitability. Index contents grant no permissions, are not stable Project Memory, and are never automatically promoted to cross-project knowledge.

## Trigger and Recovery

- On first onboarding for nontrivial development, confirm the Project Profile, repository root, and authorized external context, then scan bounded scopes relevant to the current module and public entry points. Do not wait for repository-wide discovery.
- First-onboarding changes to shared public interfaces or rules with multiple consumers scan the relevant entry points. A LIGHT profile or small file count does not cancel this trigger. Small local implementation fixes without an index may still search source directly.
- With a bound Profile and verified runtime, first query a bounded scope before editing to establish whether the index exists, is missing, or is unavailable. Neither a small task nor the absence of index files inside the workspace establishes absence. Reliable INDEX_MISSING evidence from this task permits source search when initial scanning does not apply. Small fixes with an index narrow terms and scopes, then inspect source, dependencies, consumers, and tests; JSON or help reads do not replace query-time checks. Small local fixes without a Profile/runtime retain the source-search path.
- Simple read-only questions, formatting, and unrelated tasks do not create or update indexes. `INDEX_MISSING` means no snapshot exists: when first-onboarding conditions apply and writes are authorized, scan a bounded scope; otherwise, or when creation is objectively unavailable, search source. Stop using corrupt, unknown-format, or mismatched indexes and search current source. Ordinary authorized development remains available. Format validation does not create an index, and a missing snapshot is not a runtime-environment failure.
- Use the runtime entry point, Profile, and repository root already verified for this task; do not guess project IDs or installation paths. Worktrees need their own matching Profiles. Record an explicit external index location in the existing task state and recover it later; do not silently switch indexes by modifying the Profile.

## Tool Sequence

For `query`, `maintenance.state=NOT_INITIALIZED` does not mean the tool is unavailable: apply the trigger conditions above to choose a bounded initial scan. An invalidation result of `INVALIDATED_NOT_UPDATED` still needs maintenance of checked source; do not report the update complete at that point. Suggested next operations remain subject to current task scope and authorization.

Pass `--profile` and `--repo-path` to every operation, and consistently pass `--index-root` for a custom external directory. Use the verified installed runtime, or the source package's `scripts/cp-runtime.py`.

Normally omit `--index-root` so the Profile and worktree select one location. Override it only when the task already records another exact snapshot directory. `<Profile directory>/capability-index` is the container for worktree indexes; passing it returns `INDEX_ROOT_IS_CONTAINER_OMIT_OVERRIDE`. Remove the override and retry rather than creating a second index that bypasses existing state.

| Point | Operation | Required check |
|---|---|---|
| Initial relevant scope | `capability-scan --scope <directory-or-file>`; scopes repeat | Candidate count, coverage, limitations, and actual cost; no semantic approval |
| Before development | `capability-query --term <meaning-keyword-or-symbol>` | Default five candidates; verify source, permission/state/contracts, and old uses; semantic_reuse_approved always remains false |
| Budget exhaustion | `capability-scan --resume` when pending paths exist | Matching baseline; unseen DIRECTORY_BUDGET tails need narrower explicit scopes, not a claim of full coverage |
| Recoverable change node | `capability-invalidate --changed-path <path> --expected-revision <current>`; paths repeat | Include source, tests, lockfiles, exports, and configuration; a partial dependency graph cannot prove other modules are unaffected |
| Add current observations | Scan bounded supported source paths actually checked | Unread is not verified; unchanged facts cause no writes; another branch's missing file does not establish removal |
| Semantic statement, another language, or migration | `capability-register --entry <entry-json> --expected-revision <current>` | Preserve existing IDs and evidence-backed summaries, boundaries, and references; same ID/new path is an explicit migration mapping |
| Explicit lifecycle change | `capability-lifecycle --entry-id <id> --lifecycle <state> --reason <factual-reason> --expected-revision <current>` | Provide verified grounds; deprecated entries are not default choices |

Start a new registration with the [minimal entry template](../assets/templates/CAPABILITY_ENTRY.template.json). For an existing entry, copy the query candidate, remove output-only `current_check`, and retain schema fields. Rereading hashes does not verify business statements. Never invent consumers, tests, or boundaries.

Format validation from `capability-validate` does not replace source checks. On revision conflicts, reread and merge still-valid discoveries rather than blindly overwriting. For `COMMIT_UNCERTAIN`, inspect disk state first. Explicit recovery uses the raw current-file hash and `capability-recover`; never automatically overwrite corrupt or unknown-version records.

## Decisions, Updates, and Cost

Apply [Component and Module Reuse](component-module-reuse.md) for suitability and maintenance tradeoffs. Existing task summaries link candidate IDs, decisions, checked scopes, and unknowns. Link source facts rather than copying the index or creating another full report.

The coordinator alone merges shared-index writes; subagents return discoveries without appending shared memory. Update only for added, extended, moved, deprecated, or context-affected capabilities. Stable project norms still require existing projection and human review; one successful reuse does not make future reuse mandatory.

Before closing, check affected indexed entries and newly added public capabilities. Invalidate changed paths, then scan the union of inspected changed source paths and stale candidate source paths actually checked and adopted after querying, even when the reused source itself was not edited. Read back the result; unrelated, unused, or uninspected entries stay pending with specific reasons. Refreshing location hashes never approves semantic reuse. Invalidation alone establishes that old conclusions are unusable, not that new locations or hashes are current. Subagents return changed paths, adopted stale candidate IDs, and unchecked items for the coordinator to merge. Use one sentence in the existing summary to distinguish updated, no update needed, pending verification, or pending coordinator merge; do not add a separate report.

Load the default candidate count, not the entire index. Expand terms or scopes only for specific evidence gaps. Add no fixed reviewers, model calls, or background scans. Prefer existing command counters for enumeration, reads, bytes, and time. Unavailable tool-call or token counts stay UNKNOWN. The index itself does not change hook or budget protocols; the explicit optional gate below integrates separately with the host.

## Explicit Project Process Gate

Disabled by default. After explicit project opt-in, run `capability-gate-enable` through the verified runtime. Omit revision for first creation; for an existing policy, read `capability-gate-status` and supply its exact `--expected-revision`. Disable with `capability-gate-disable --expected-revision <current>`, retaining indexes and receipts. Enabling neither grants business writes, commits, or deployment nor creates an index.

The host must load and trust the relevant package hooks and supply stable session/turn identities. An enabled setting does not prove execution. Only a real UserPromptSubmit creates the origin; never invent IDs or create it through a CLI. Use the injected binding, never another task's IDs. A custom `--gate-root` must match the host's startup `CP_CAPABILITY_GATE_ROOT`.

1. Before writing, run `capability-task-prepare --scope <file> --term <keywords>`; repeat scope for more files. Cold indexes receive a bounded initial scan by default. Only a local implementation fix in one existing file may supply a source-based `--local-only-reason`; public API extensions, new features, or coordinated consumer changes do not qualify merely because they are small. The gate checks the accumulated prepared scope: multiple or new files require bounded scanning. Expand a cold exception before changing any prepared file; initial scanning cannot be certified retroactively. File count does not establish business semantics, which still need source checks and tests.
2. Inspect candidate source, consumers, and tests, then apply reuse decisions. Controlled native write tools reject missing preparation. Other execution paths still require current evidence checks; do not claim every write is intercepted in advance.
3. Store the decision JSON and other task-only helper files in the already-authorized external context containing the Profile, with task-specific names. Keep them outside the repository and never overwrite runtime-managed Profile, index, gate, or receipt files. New project tests are business changes and still need scope preparation before writing. After changes, run `capability-task-finish --decisions <absolute-external-JSON-path>`. Cover every `required_decisions` ID with `{id,choice,reason}`, where choice is reuse/extend/extract/independent/unused. Declare actual adoption. Finish refreshes adopted stale sources even when they were not edited.
4. Run `capability-task-check` for current evidence. Stop rereads receipts and allows at most two repair attempts for missing steps. No progress or hard limits stop continuation. Missing pre-change evidence cannot be signed after the fact.

PASS means current controlled-process evidence is valid; `semantic_reuse_approved` remains false. Source and tests establish suitability and compatibility. NO_CHANGE covers only bounded Git-visible unchanged scope; retain PARTIAL, BLOCKED, FAILED, and CANCELLED separately. A cancelled task cannot become PASS; it needs a new real task origin. The gate cannot retract displayed model responses or establish completion from their claims.

The current source has real UserPromptSubmit and Interrupt evidence on Codex CLI 0.153.4. Configuration reading on 0.149.1 retains Stop but ignores Interrupt. Other hosts, Desktop loading, plugin installation, and individual write tools need separate acceptance; unverified cases cannot claim equivalent protection. Historical six-event compatibility evidence does not establish cancellation support.
