# Script decisions and bounded flexibility

For new Codex Desktop roots using `desktop-g6-deterministic-v1`, keep the main agent's selection. Reviewers, Workers and Explorers use the nine GPT-6 Luna/Sol/Astra low/medium/high profiles. Keep 5.6 for explicit compatibility and historical replay. Never silently change an old root's algorithm, charges or outcomes.

## Execution

1. Use the installed Desktop dispatch-preparation entry to obtain script-collected facts, default profile, allowed adjustments, shared budget, gate states and next action.
2. Execute `exact_tool_parameters` and `next_action`, explicitly specifying model and reasoning_effort. Models may interpret tasks, generate content, discover risk and propose adjustments, but cannot change parameters while reusing an old permit.
3. Submit structured proposals for additional reading, scope splitting, ordering, effort or model changes. Scripts recalculate and issue a new decision. Missing lengthy rationale or gain evidence does not stop the default task.
4. The controller atomically reserves before dispatch and records actual creation, terminal, cancelled and unknown states. Resume the same handle while it is running or its outcome is uncertain; do not create a duplicate call or claim a free recovery.

Known lookup, extraction and mechanical work defaults to Luna/low; ordinary or unknown work to Sol/medium; known cross-domain adjudication may use Astra/medium. Follow the final script result. File counts, line counts, path matches and one failed check are signals, not proof of difficulty or a defect. Automatic xhigh/max/ultra remain forbidden.

## Missing evidence and gates

Keep every project-owned active gate enabled. Missing rationale, quality/gain cards, historical samples, noncritical material or optional checks returns a default, degraded or other executable next action without temporarily disabling a gate. Downstream Hooks cannot turn the same missing evidence back into a qualification rejection.

Unknown capability information does not mean every model is unavailable. Prefer host-provided capability information; insufficient proof alone uses a bounded default attempt with uncertainty recorded. When the interface is actually unavailable, all profiles are explicitly unavailable or the budget is exhausted, report the real limit and continue feasible local work without claiming a dispatch occurred.

Confirmed authorization, safety, project-identity, ledger, budget or payload-integrity violations restrict their affected action. A default profile cannot grant missing user authority, and this policy does not disable external platform permission or trust controls.

Keep permission to continue separate from verified success. Missing isolation proof supports only logical-readonly, and missing results cannot become PASS. When the user expressly requires system isolation that the host cannot provide, restrict that action only.

## Budget and flexibility

- Scripts compute authorized capacity, completed charges, in-flight reservations and required future holds. Never charge one call twice or reset the root budget through splitting.
- Planning units are versioned allocation weights, not actual credits or quality scores. Unknown measured cost remains UNKNOWN.
- Read adjustment limits, concurrency, depth, retries and backoff from the runtime policy. Necessary downgrades do not consume upward-adjustment slots. If only a more expensive GPT-6 profile is available but the existing budget allows it, the script may choose the cheapest available profile and record the capability fallback.
- Model risk and task-type proposals remain semantic advice, not verified facts or user authorization.
- Reserve only genuinely required future work that satisfies its constraints. Missing evidence does not initiate a qualification study, and one failure does not force high effort.
- Do not review unchanged material repeatedly without new information. Classify recoverable failures and bound them by remaining budget and total time.

## Computable standards and natural observations

Scope metrics record definitions, units, sources, calculation versions and missing-value behavior. File counts and path matches are scope signals only. Keep authorization constraints, planning budgets, task fit and evidence status separate rather than combining them into one score. Fact collection returns available material within a whole-operation deadline and preserves UNKNOWN values.

Required work converts its own future hold into an in-flight reservation without charging twice, and must use an allowed capability profile. Verified no-start attempts may be prepared again while retaining their attempt count. Registered splits share an origin_work_item_id adjustment allowance. Work without trusted lineage shares the root allowance, so renaming cannot reset it; default dispatch remains available.

Stop derives single-root observations from the existing journal: attempts, charged and in-flight planning units, native outcomes, and reservation-to-terminal-record latency by approved profile and role. Retries are not independent tasks, and native PASS is not proof of business quality. Quality and actual-cost metrics remain UNKNOWN without finalized adjudication or a cost source. Observation creates no model calls or automatic policy changes, and collection failure does not block authorized work.

## Compatibility and replay

Read the root's bound policy first. Existing V3/V4 ledgers retain the [historical routing rules](reviewer-model-routing.md) and frozen contracts. New defaults neither require their statistical qualification nor classify missing legacy cards as violations. A verified same-chat handoff preserves historical charges, unresolved records and late-event ownership.
