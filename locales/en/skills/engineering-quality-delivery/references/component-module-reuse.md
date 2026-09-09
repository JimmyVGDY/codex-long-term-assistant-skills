# Component and Module Reuse

Use when adding features, fixing bugs, refactoring, or changing shared implementations. Read-only explanations and formatting without behavior changes do not trigger it. The goal is to use existing capabilities correctly and preserve existing uses, not maximize reuse or abstraction counts.

## 1. Locate Before Deciding

Before editing: locate existing capabilities → read implementations and consumers → assess suitability → choose an approach → validate new and existing behavior.

When a project index already exists or this is first onboarding for nontrivial development, follow the [capability-index workflow](capability-index-workflow.md) for queries/bounded discovery, source checks, and postchange maintenance. Reading that reference does not require another Skill. A simple fix without an index uses bounded source search directly.

- Start with the target module, neighboring modules, shared directories, and existing documentation. Search by functional meaning, similar flows, symbols, exports, and actual callers; names or directory labels alone cannot establish that no suitable implementation exists.
- Read candidate implementations, representative consumers, related tests, and examples. Confirm configuration, dependency versions, runtime, and deprecation status. Indexes are leads; return to source when stale or inconsistent. Do not build a repository-wide index for one local change.
- Expand along dependencies and callers only when evidence is insufficient. Local checks suffice for simple work; do not mechanically scan the entire repository.
- Distinguish “not found within the searched scope,” “found but unsuitable,” and “not yet checked.” The last is not a reason to create a new implementation: complete checks relevant to the decision first. If reading is objectively blocked, state unknowns and their impact rather than claiming candidates were ruled out.

## 2. Choose the Minimum Sufficient Approach

Assess responsibilities and business meaning, inputs/outputs, error semantics, state and side effects, permissions/tenancy, resource lifecycle, dependencies, and runtime boundaries.

| Decision | Condition | Minimum evidence |
|---|---|---|
| Reuse directly | Existing implementation is suitable | File/symbol and use site or caller example |
| Extend an existing implementation | Same responsibility with a compatible addition | Extension point, original defaults, affected consumers |
| Extract a shared module | Multiple uses share semantics and joint maintenance has a concrete benefit | Common rules, variation boundaries, migration scope |
| Create independently | No suitable implementation within scope, or reuse increases risk | Searched scope, reasons candidates are unsuitable (if any), new responsibility |

A local fix may retain its current implementation; do not invent work to fit these four decisions. Similar code does not establish identical business meaning. Do not cross permission, data ownership, or lifecycle boundaries merely to reuse code. Avoid universal components full of business switches, pass-through wrappers, or global utility modules. Accept justified independent implementations, leave unrelated duplication alone, and do not automatically extract cross-project libraries.

### Maintenance Cost

First satisfy semantic, permission, contract, state, and lifecycle constraints, then compare long-term cost among feasible approaches:

| Dimension | Main question |
|---|---|
| Change coupling and ownership | Do consumers evolve independently, and which module owns the common rule? |
| Interface and dependencies | Does reuse add business switches, hidden ordering, pass-through layers, cycles, or version lock-in? |
| Understanding and diagnosis | Are rule ownership, call chains, and error locations clearer? |
| Impact and validation | Which old uses change and what direct tests are needed, without mocks hiding boundaries? |
| Migration and recovery | Are consumer migration, coexistence, and rollback controlled? |
| Runtime resources | Does reuse add I/O, connections, memory, caching, or concurrency coupling? |

For ordinary work, state the main tradeoff briefly. For cross-module or disputed choices, compare two or three genuinely feasible approaches and distinguish evidence, inference, and unknowns. Do not read full Git history without a concrete need, invent alternatives for formality, or use a mechanical aggregate score. Fewer lines, more indexed entries, and higher reuse rates alone do not prove maintenance savings.

## 3. Preserve Existing Uses

- Identify affected consumers through public exports and call chains. Record coverage limits for dynamic registration, plugins, and external consumers; do not claim complete coverage when it is unknown.
- Unless explicitly requested otherwise, preserve existing parameters, defaults, return values, error behavior, and side effects. Prefer compatible defaults for new capabilities.
- Before changing a shared implementation, inspect existing contract/characterization tests. Where a risky existing behavior is unprotected, prioritize a test that demonstrates it. Do not add implementation-mirroring tests for low-risk reversible changes.
- After editing, validate new uses and affected old uses, covering permissions, errors, state isolation, cancellation, and resource release as warranted. A successful build or entirely mocked tests alone do not prove compatibility.
- After extraction or migration, remove implementations replaced by this change and confirm consumers actually use the common rule. Shadowing same-named definitions, leaving unreachable old code, or switching only some callers does not complete the migration. Limit cleanup to code replaced by this change.
- Describe migration, version coexistence, stopping, and rollback separately for breaking changes. Without corresponding authorization, do not fold them into routine reuse work.

## 4. Concise Evidence and Review

In the existing task summary or review packet, record “searched scope and candidates → decision and reason → consumer impact → validation and unknowns,” linked to files/symbols or call chains. One sentence suffices for simple work; do not require new documents or runtime fields. Recheck affected decisions and evidence when the baseline changes.

When relevant indexed capabilities change, the coordinator merges invalidation and updates at a recoverable node. Link IDs, observation scope, and the main maintenance tradeoff in the existing summary; do not copy the whole index. Unrelated changes add no records, and indexes never automatically become stable memory.

When existing review criteria trigger review, the functional reviewer checks missed capabilities and shared business meaning, the compatibility reviewer checks existing consumers and shared state, and the test/delivery reviewer checks evidence for new and existing uses. A duplication finding must locate a suitable existing implementation and concrete risk; abstraction preferences alone cannot block delivery. This rule adds no mandatory reviewer and changes neither review budgets nor authorization boundaries.

## 5. Validating Rule Effects

Links, package checks, and localization prove distribution integrity, not reliable agent execution. Behavioral replays use independent initial workspaces and inputs describing only the task goal. Preserve before/after rules, model/effort settings, scenario baselines, and actual results; do not give expected answers to the executing agent. Report discovery, duplication, incorrect reuse, old-use regressions, and additional reading/execution cost separately; unknown remains unknown. Passing a finite sample does not establish guaranteed reuse across all projects.
