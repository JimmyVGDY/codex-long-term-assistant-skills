# GPT-6 routing V4 data and transaction contracts

This contract targets Codex Desktop. Internal management, build and installation
scripts are not a standalone CLI product. V4 separates model/scenario qualification,
effort or model-switch gains, and resource approval. Frozen four-tier-v1 and
reviewer-matrix-v2/v3 readers retain their original interpretation.

## Trust and provenance

JSON reads are bounded and reject duplicate keys, nonfinite numbers, unknown fields
and invalid types. Digests establish content consistency, not issuer authentication.
Publication approval, provenance and current availability are verified separately.

- CardBundle binds project/repository identity, policy and algorithm, scenario,
  origin, validity window, experiment reference and derived cards.
- Experiment binds the issuer task/baseline, fixed rubric, preregistered comparisons,
  significance allocation, cases, repetitions, samples and parent finalization.
- CardPublication binds the bundle/experiment, issuer approval, consumption scope,
  validity, status and revision.
- RootBinding binds the consuming task to its Project Profile, envelope, policy,
  Desktop session and source documents.

Issuer task/baseline and consumer task/baseline are distinct. `issuer-only` confines
consumption to the issuer task; `project-bound-reuse` permits subsequent tasks with
the same project/repository, policy, algorithm and approved scenario contracts.
Each consumer permit, result and Evidence still binds its current code baseline.

`make-effective` approval is checked and consumed once when publishing the exact
bundle and consumption scope. A reusable publication does not consume that approval
again in each later task. Each new reservation checks the pinned publication reference
and revision, expiry and revocation. A changed project, scenario or runtime contract
requires new evaluation/publication approval.

Only `synthetic` and `desktop-evaluation` origins are accepted. Synthetic data is
test-only. Native evaluation requires verified Desktop calls, parent grading and
publication approval before production consumption. `EVALUATION` itself grants no
production qualification. Readers recompute qualifications and quality gains instead
of trusting `qualified=true`.

Publication approval consumption and publication storage are separate files. A crash
after consuming approval fails closed; retry needs separately issued approval. Hashes,
local locks and workflow approval do not provide OS isolation or external signatures
against an actor able to replace all local state. Backend model identity is not collected.

## Eighteen combinations and scope

The catalog explicitly names GPT-5.6 Luna/Terra/Sol and GPT-6 Luna/Sol/Astra at
Low/Medium/High. Profile IDs include the generation. Existing `luna-low` and other
legacy IDs keep their historical meaning. Default V4 production candidates are the
qualified GPT-6 subset. GPT-5.6 Luna High and Terra Low enter evaluation without being
retroactively inserted into old policies.

Scenario identity covers role, normalized phase, semantic/reasoning/risk levels, tags,
context bucket, tool profile, speed mode and prompt digest. `repair` is normalized
from post-review plus repair kind. Qualification never transfers merely because the
model name matches. Different projects never share a calibration cohort.

## PhasePlan/1 and lifecycle

PhasePlan contains schema, plan ID, revision, identity and slots. Policy/card sources
are pinned in the root ledger; initialization, revisions and selections persist complete
allocation witnesses. A slot contains:

- Unique slot ID and exact scenario.
- `independence_required`, mandatory for risk levels 2/3.
- Dependencies and `always` or `repair-after-post` condition.
- Full options with profile, qualification/cost references and resource vectors.
- Status, active reservation, accepted result and waiver Evidence references.

The vector is units, attempts, Astra attempts and Astra High attempts. A witness
selects one real option for every pending obligation. It cannot combine separate
componentwise minima. Search exhaustion returns `PHASE_PLAN_SEARCH_LIMIT`, not
proof of infeasibility.

| Event | Atomic projection |
|---|---|
| INITIALIZED | Fix slots, references and a feasible witness |
| PLAN_REVISED | Increase revision; retain consumption, scope and active work; recompute holds |
| DISPATCH_RESERVED | Consume permit, create reservation, move PENDING→RESERVED |
| HOST_RECEIPT / HOST_OBSERVED | Associate an exact call and agent; do not infer business success |
| RESULT_ACCEPTED | Validate result identity/scope; save result and complete this attempt's obligation |
| SLOT_WAIVED | Release a conditional repair only after the related passing post-review result |
| NOT_STARTED_RELEASED | Refund units only from trusted not-started proof; attempts remain consumed |

A uniquely associated stop marks the reservation COMPLETED and its slot
AWAITING_RESULT in the same projection. Stop-before-created is stored unassociated
until the exact receipt arrives. Duplicate callbacks are idempotent; conflicting
terminals fail; late start cannot regress completion. Generic status, missing callbacks,
timeouts and cancellation requests prove neither completion nor non-start.

A task-tree receipt must exactly match the preregistered /root/task name. When a
callback uses an internal ID, the adapter reads only the first identity record from
the host-provided agent_transcript_path under the current CODEX_HOME/sessions, with
a 128 KiB limit. Parent session, child ID, repository, role, depth and task name must
all match. It never scans the body, inspects runtime model fields or guesses by timing.
This observed metadata shape is not a stable public interface; unsupported paths or
shapes remain unassociated and cannot complete an attempt or authorize a refund.

An explicit CANCELLED/FAILED/PARTIAL/BLOCKED host outcome only permits an incomplete
result. UNKNOWN supplies no review verdict: a separate result must pass identity,
current-baseline, completed-scope and content checks, and never rewrites that host
outcome to PASS. A blocking post result completes the initial review and enables its
reserved repair slot; repair results explicitly supersede the original blockers.
Blocking pre or repair results, and all incomplete results, leave their slot PENDING.
Retries need the latest result and genuinely changed evidence, baseline or packet.
Consumed units and attempts remain charged. A new root cannot reset an unfinished
budget. Mandatory slots cannot disappear merely because resources run out. Plan
revision cannot mutate active or completed slot scope.

## Selection and one-use permission

Selection binds the normalized request and message digest, identity, policy, cards and
publication revisions, capability, plan/resource revisions, baseline, anchor, winner
and reservation amount. It is not dispatch authority.

The coordinator prepares a permit with a random 256-bit nonce; only its digest enters
the journal. A named dispatch key and a `CP_REVIEW_DISPATCH/2` message prefix are
exclusive alternatives. Independent context is explicit. Permit scope includes slot,
attempt, registered role, exact model/effort, message and evaluation case where applicable.

Under one root lock, admission reloads current sources, recomputes the same choice,
checks all limits and future holds, then appends one event consuming permission and
creating the reservation. Resource revision is distinct from journal sequence, so
preparing metadata does not invalidate its own resource snapshot.

| Condition | Result |
|---|---|
| Same host call and permit, still RESERVED without receipt | Return the same reservation without a second charge |
| Same permit, different call | PERMIT_ALREADY_CONSUMED |
| Same call, different permit/tuple | HOST_DISPATCH_COLLISION |
| Receipt or start already exists | ATTEMPT_ALREADY_STARTED |
| Previously released attempt | RELEASED_ATTEMPT_REUSE |
| Changed source, capability, baseline or resource/plan revision | Refuse stale dispatch; never silently choose another winner |
| Unknown cancellation or missing receipt | Keep the unresolved attempt and reservation |

Local reservation idempotency does not prove that the host executes exactly once.
Recovery replays complete ledger events and rebuilds the review projection without
inventing model results.

## Statistical and resource decisions

First filter role admission, Desktop availability, exact scenario qualification,
comparable cost and resource feasibility. The economic anchor minimizes planned cost,
then latency, then profile ID. Optional upgrades need a directly paired quality-gain
lower bound of at least 3 percentage points. Economy keeps the anchor; balanced caps
cost at 2× and latency at 1.20×; deep may spend more within the fixed root limits.
Risk 3 selects deep behavior without extra resources or a mandated model/effort.
Within 1 percentage point of the best gain, prefer lower cost.

Quality and false-block comparisons use exact binomial bounds on paired discordant
events with a preregistered comparison family. Repetitions aggregate by case/task
cluster; reusing receipts or splitting a task cannot inflate independence. The statistics
library also provides deterministic paired resampling; reports must state whether that
calculation actually ran. Production selection uses approved cost-card planning values,
never treating proxy units or empirical intervals as a hard real-billing limit.

## Management and compatibility

`scripts/routing-v4.py` manages repository-external state and artifacts:

| Commands | Purpose |
|---|---|
| init / bind-desktop / status / retire-desktop | Root ledger, session/repository binding, readback and closed tombstone |
| review-init / prepare / result-template / result / review-status / review-close | Ownership, choice, V6 result validation and V9 conclusion |
| eval-plan / eval-suite / eval-request / eval-result / eval-advance / eval-assemble | Preregister paired scenarios, freeze an experiment suite, create exact requests and retain cumulative accounting |
| bundle-build / publish / revoke-publication | Derived cards, scoped approval consumption and revocation |
| sample-pending / sample-finalize / sample-report | Pending observation, finalization evidence and source-verified grouping |
| revoke-prepare / close | Revoke unconsumed permission and close the root |

The manifest freezes prompt, gold and rubric digests plus the comparison family.
Reviewers receive task material without gold answers. Parent grading records structured
booleans and artifact references; Hook and ledger records never save raw material.
A trial result's pass means capture is complete; model correctness is `grade.passed`.
Complete trials do not imply model qualification. Missing planned trials fail assembly.

eval-suite freezes up to ten preregistered scenario manifests and their exact trial
total in one root source. Each group runs its declared comparisons, without crossing
every profile with all groups' cases. Case identities must be unique; costs for the
same scenario/profile cannot conflict. Groups share one cost basis, cumulative spend
and root limits. Gold, rubrics and native receipts retain their original protocol;
qualification samples cannot be combined across groups.

Astra has a fixed inflight limit of one, separate from root max_parallel and cumulative
astra_attempts. Status exposes astra_active and astra_parallel_available. RESERVED and
STARTED attempts count until a trusted associated terminal event or a proven not-started
release. Completion refunds neither units nor attempts; not-started proof only refunds
units. Atomic reservation rechecks the category limit, even if a selection snapshot is
misleading. Ordinary profiles retain parallelism within the root limit.

Current cost cards may use approved `declared_proxy` amounts. Production rejects
`measured_codex_credits` without attributable Desktop billing evidence. Observed trial
latency includes orchestration and callback overhead. Resource reports never change cards.

Sample V4 reports reload ledger, immutable V6 result and finalization Evidence.
Identical records deduplicate; conflicting records fail. Finalization checks the current
baseline; historical reports check pinned provenance and the recorded baseline without
claiming current-code acceptance.

Desktop root registry conflicts and corruption fail closed. Other roots/projects do not
scan or borrow that binding. A closed tombstone continues to resolve the closed ledger,
preventing silent fallback or budget reset. This remains logical workflow control.

V4 introduces Selection V2, Budget V4, Review State V9, Result V6 and Sample V4.
Existing formats and cost formulas remain frozen. Recovery reads the bound policy
before model admission. Acceptance separately covers source, package, installation,
loaded runtime, native dispatch and public release. Synthetic tests never establish
real model quality.

While a V4 root binding is active, followup_task, send_message, send_input and resume_agent cannot start another review or inject trial material. Admission rejects these calls. A new round requires a fresh independent dispatch and permit. Pause or cancellation does not imply a refund.

`add-evidence` appends only current-baseline Evidence for the same project, task and existing scenarios. It cannot replace prior references, policy or spent resources. The event advances the selection revision, invalidating prepared permits; revoke unused permits before recalculating. A stale-baseline result may be retained only as incomplete and cannot close as PASS.
