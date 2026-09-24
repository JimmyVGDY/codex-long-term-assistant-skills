# Desktop model selection, reasoning gains and budget approval

## Scope and activation

Codex Desktop is the only supported product surface. Internal management, build and
installation scripts do not constitute standalone CLI support. The parent keeps its
selected model. The V4 Reviewer catalog contains six models at Low, Medium and High:
18 evaluation combinations. Its new production pool contains the nine GPT-6
combinations, each requiring qualification for the exact scenario. Catalog membership,
availability and affordability do not establish review quality.

V4 is explicitly activated as `reviewer-matrix-v4 / quality-gain-routing-v1`.
Missing approved scenario qualifications return `CALIBRATION_REQUIRED`. Synthetic
fixtures cannot supply qualification, and an existing ledger cannot switch to V3.
Existing tasks and compatibility paths explicitly selected before initialization use
the [frozen V3 rules](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/master/locales/en/skills/multi-agent-independent-review/references/reviewer-model-routing-v3.md).
V1/V2/V3 policy files, resource semantics, ledgers and result readers remain supported.

## Model positioning and evaluation hypotheses

Official positioning guides case selection; local paired evidence establishes suitability.

| Model | Positioning and priority evaluation scope | Compatibility decision |
|---|---|---|
| GPT-6 Luna | Focused, high-volume, cost-sensitive work; mechanical checks and bounded logic | New candidate; qualify Low/Medium/High separately |
| GPT-6 Sol | Complex coding and agentic workflows; business logic, state transitions and contracts | New candidate; do not merely rename the old Sol weights |
| GPT-6 Astra | Difficult end-to-end reasoning; cross-domain constraints and evidenced conflict resolution | New candidate; risk alone never mandates Astra/High |
| GPT-5.6 Luna | Historical cost-sensitive baseline | Preserve existing Low/Medium; High enters evaluation only |
| GPT-5.6 Terra | Historical capability/cost balance | Preserve existing Medium/High; Low enters evaluation only |
| GPT-5.6 Sol | Historical complex professional-work baseline | Preserve Low/Medium/High compatibility paths |

Sources: [official model catalog](https://developers.openai.com/api/docs/models/all)
and [model selection guide](https://developers.openai.com/api/docs/guides/model-selection).
This table does not claim measured local superiority between any pair.
Worker and Explorer retain their original four profiles, capped at `gpt-5.6-terra + high`.
Automatic dispatch never uses xhigh, max or ultra.

## Marginal reasoning gains

Evaluate Low for well-evidenced, short and bounded decisions; Medium for multi-step
reasoning; High for competing hypotheses, complex state and interacting constraints.
These are hypotheses, not fixed quality points awarded for an effort name.

Preregister same-model Low→Medium and Medium→High comparisons separately from
cross-model comparisons such as Luna High→Sol Low or Sol High→Astra Low. Keep materials,
tool permissions, rubrics, cases and repetitions fixed. More reasoning or a different
model may offer no gain or cause more false positives. Requested model/effort is
recorded without reading or inferring the backend model identity.

## Three decisions

1. **Qualification:** match role, phase, semantic/reasoning/risk scope, tags, context
   bucket, tools, speed mode and prompt contract. Severe misses and boundary violations
   cannot be offset by additional ordinary findings.
2. **Gain:** among qualified, feasible candidates, choose the lowest planned cost as
   the economic anchor; break ties by latency, then profile ID. An effort increase or
   model switch requires paired evidence for the same scenario.
3. **Budget approval:** selection is not permission. The Hook rechecks identity,
   revisions, baseline and evidence, then consumes the permit and reserves resources
   in one root-ledger transaction, preserving future pre-review, post-review and repair.

| Mode | Rule |
|---|---|
| economy | Select the economic anchor |
| balanced | Gain lower bound at least 3 percentage points; at most 2× anchor cost and 1.20× latency |
| deep | Select evidenced quality gain within actual limits; prefer lower cost within 1 percentage point of the best gain |

Risk level 3 uses deep without granting extra budget or mandating the most expensive
combination. Units, attempts, Astra attempts, Astra High attempts, concurrency, depth,
role and phase limits are distinct. Future holds require one feasible whole allocation;
componentwise minima from different model options cannot be combined.

## Evaluation and cost evidence

Thirty independent cases is only a count floor. The absolute pass-rate floor is 90%,
paired noninferiority margin 5 percentage points, and false-block difference margin
2 percentage points. Exact intervals allocate significance across the preregistered
comparison family. Insufficient intervals still fail qualification; additional comparisons
usually need additional cases. One receipt cannot stand for multiple calls, and one
task cannot be split into independent cases.

Cost cards separate planned cost, reserved units and latency. The current Desktop
adapter lacks attributable per-call billing receipts, so it permits explicitly labeled
`declared_proxy` values. API prices or aggregate account usage cannot masquerade as
per-call Desktop cost; production loading rejects unsupported `measured_codex_credits`.
Trial latency measures reservation to stop callback, including orchestration overhead.

Completing an experiment, computing qualifications and publishing cards are separate
steps. Production needs complete native call provenance, parent grading and approval
bound to the exact bundle and consumption scope. Expiry, revocation or revision changes
block subsequent dispatch.

## Desktop binding and recovery

`scripts/routing-v4.py` is internal Desktop plugin tooling. `bind-desktop` registers a
ledger by root session and repository fingerprint, without trying to mutate the Desktop
parent environment from a subprocess. Conflicting explicit and registered bindings fail.
Closed entries retain tombstones to prevent budget resets or silent policy-only fallback.

Dispatch uses either an exact named key or an exclusive `CP_REVIEW_DISPATCH/2` nonce.
The message digest, independent context, role, tuple, baseline and phase are bound to
the permit. Unknown receipts stay unassociated. Generic status, timeouts and cancellation
requests are not refund evidence. Trusted not-started proof can refund units, never
attempts. Root-ledger replay handles duplicates and out-of-order callbacks.

| V4 object | Version |
|---|---|
| Root budget / Review state / Review result / Observation sample | 4.0 / 9 / 6 / 4.0 |
| Phase plan / Desktop capability / Evaluation manifest | phase-plan/1 / desktop-capability/1 / routing-evaluation/1 |

V9 reconciles immutable results with the root ledger and persists a conclusion. Pending
permits, active calls, missing results and unresolved blockers prevent PASS closure.
Observation reports reload ledger, result and finalization evidence, separating project,
policy, scenario and cost basis. Historical observations do not establish current-code
readiness and never automatically alter routing, budgets or configuration.

See the [data and transaction contracts](MODEL_ROUTING_V4_CONTRACTS.md) for details.
