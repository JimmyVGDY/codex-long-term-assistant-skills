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

## Review reader transport version 2 (local candidate)

`desktop-authoritative-context/2` is explicit for a new evaluation root; `/1` remains
the default. The immutable Budget 5 runtime mode selects the interpreter. Existing
roots are never upgraded in place. Frozen V3 defaults and the production coverage
gate remain unchanged; internal management scripts add no standalone CLI support.

- One controller generator owns the fixed command, structured parameters and full
  `functions.exec` program. Ordinary Windows paths use forward separators; JSON
  serialization preserves special namespace paths without model-owned escaping.
- Each child has at most three reader attempts within five seconds of the first.
  Only a pending creation receipt or a successful output that is a strict prefix
  of the expected bytes permits recovery. Unknown output, nonzero exit, identity,
  permission, baseline, material hash and command failures terminate. Duplicate
  native events are idempotent. A new model dispatch remains a charged attempt.
  The window bounds both retry admission and completion acceptance. Late material
  remains a delivery fact but cannot make recovery successful; this does not claim
  forcible interruption of operating-system I/O.
- Original failures, recovery reads and delivery evidence remain in the journal.
  Old `/1` forbidden retries are not regraded. Reader recovery does not charge a
  second model dispatch.
- Models supply five semantic fields. The controller supplies fixed initial
  finding governance fields. Removing the copied nonce requires a trusted native
  child transcript path, linked header, material delivery and unique exact final
  response. Only response/semantic hashes enter the journal. Missing or conflicting
  proof stays incomplete; the parent cannot invent it or override cancellation.
  Initial association pins canonical transcript location and stable file identity;
  final header/body bytes come from one open handle. A copied header at another path
  or replacement of the original file cannot take over proof. Normal appends remain valid.
  Internal `failure-accounting` produces an explicit controller-only record only
  for a stopped call with a verifiable failure condition. It can only be incomplete,
  never rewrites the original response or replaces verified success, and records
  native-response verification separately.
- `desktop-evaluation-trace/3` includes final-response and recovery references.
  Legacy qualification consumers reject it. Native acceptance and production
  qualification remain separate gates; synthetic tests cannot grant either.
- Report delivery, protocol acceptance, conditional semantic accuracy, scoring
  coverage and full-workflow success separately. Failed reads remain in the latter
  denominator. Excluded/failed attempts retain their resource costs, unknown costs
  remain unknown, and proxies are not billing.

Six clarified cases have new identities, provenance hashes, explicit input domains
and executable gold verification. Original materials, golds and decisions remain
historical. Local verification does not approve a default model migration.

## 9. Qualification evidence for reader protocol two (in development)

Explicit `routing-experiment/2` consumes `desktop-evaluation-trace/3` or `/4`,
without mixing versions in one experiment. Experiment `/1` rejects both. The new
consumer verifies native answers, recovery, delivery and accepted results. `/4`
separates original-answer proof from parsed semantics: native incomplete or
malformed answers may count as failed samples, never passes. Controller-only
accounting without native answer, delivery and tool proof is not a model sample.

`routing-trial-result/2` binds an immutable parent grade to the existing ledger's
accepted-result reference, raw answer, case, gold, rubric, requested profile and
repetition. The original ledger owns model results and spending. Grading never
rewrites those facts or fabricates native receipts. Hash persisted gold/rubric
bytes, rather than a string before operating-system newline conversion. Equal
answer bodies may come from distinct native calls: share body storage by hash,
but keep an attributed envelope for each dispatch.

Internal `qualification-size-plan` uses the unchanged exact intervals to plan
for zero discordance. One comparison needs 252 independent clean cases and 99
independent quality cases under that assumption. Clean cases are a subset, not
additional evidence. Planning does not replace actual bounds, the 90% quality
floor, critical-failure checks or independence. Observed gains/losses still use
the original algorithm; never shrink a comparison family or split repeated
problems to manufacture a pass.

Internal `qualification-grade` and `qualification-assemble` produce unpublished
evidence only. New bundles bind `qualification_source`: exact study and complete
trial-source documents plus a recomputable audit reference. Publication and
consumption reread every registered journal and grade. Missing segments, active
or ungraded calls, changed references and reused calls cannot pass; a successful
subset is insufficient. Production denial, the V3 default, 5.6 compatibility and
explicit model/effort on every automatic dispatch remain unchanged. Complete
evidence alone never activates a default.

`qualification-study/1` preregisters every case/profile/repetition unit, reviewed
independence Evidence, segments and aggregate resources. Each segment has at most
64 attempts; segment capacities cannot exceed the total allocation. The same
problem, root cause or identical prompt cannot create extra independent clusters.
Native roots bind the complete study through their cost cards. Changing the plan
or opening an unregistered ledger cannot replenish it. Missing segments make
resource totals explicitly incomplete; actual billing remains UNKNOWN.

Tool proof checks original transcript location/file identity, final answer, one
controller program and the actual model-visible output. Only outer ASCII spacing
is ignored. Extra operations, hosted search, other tools and outer truncation are
rejected. Local hooks plus observed-tool verification remain logical read-only;
they are not system isolation and cannot undo side effects. See the official
[hook tool coverage](https://learn.chatgpt.com/docs/hooks).

## 10. Local default activation (inert without qualification)

`desktop-default-activation/2` requires a complete frozen qualification plan for new defaults;
`/1` remains available for historical reads and explicit recovery only.
`default-qualification-plan/1` derives21 cells from seven registered roles and pre/post/repair.
It binds complete native development screening of all18 exact tuples, a reviewed preregistered
selection, the payload digest and confirmation protocols. Confirmation compares only the frozen
GPT-6 tuple in each cell against its5.6 control; unchanged statistical gates apply, without
requiring all18 tuples to repeat formal confirmation. Development/confirmation problem, cause,
cluster or prompt overlap is rejected. Missing cells, screening profiles or complete denominators
cannot activate defaults. Worker/Explorer evaluations cannot create Reviewer qualifications.
The100 project-source and10 task-source limits remain unchanged.

Activation persists a source/task/baseline/approval/prior-pointer intent before consuming authority.
Interrupted ACTIVE or consumed-approval writes can retry the same operation without consuming again
or overwriting a different current pointer. Explicit authorized legacy restoration repairs missing
pointers and retries its own interrupted pointer publication. Expiry, revocation, changed bytes and
incomplete qualification remain fail-closed.

Current Desktop completion mirrors may omit one strictly recognized trailing memory-citation block.
The body must match byte-for-byte. Native extraction returns and hashes the entire original final,
including metadata; it never normalizes or strips model text. Such a final remains non-JSON and does
not gain a model pass or qualification.

## 11. Explicit 64KB material profile

New roots may opt into `context_profile=bounded-review-64k/1` while retaining
transport `/2` bounded recovery and native-result attribution. The profile caps
serialized bundles at 64000 bytes, reader output at 65536 bytes and artifacts at
64 per bundle. Per-file reads and total serialization are bounded; links, traversal,
changed hashes and excess size are rejected rather than silently truncated. Existing
roots without the profile retain their 8000-byte limit.

The profile uses bundle/2 and must match the root runtime. Its scenario fixes
`context_bucket=bounded-review-64k` and `tools_profile=desktop-context-reader-64k-v1`.
An 8KB qualification cannot silently graduate to it. The controller generates both
inner-reader and outer code-mode output budgets; actual model-visible output must
still match the delivery digest byte for byte. Local protocol tests do not grant
model qualification for this changed tool contract.

Desktop PostToolUse may contain a clipped display preview. The 64KB profile can
verify inner output only from the original child transcript: one matching tool
call and turn, the bound directory and exact command, successful exit, and stdout
plus aggregated output equal to the approved bytes. The preview must also match
that native event's formatted output. Missing or duplicate events, replaced files,
wrong commands or timing remain rejected. The complete code-mode program and
model-visible bytes are still checked independently. Inner proof cannot replace
that check; preserve the leading `// @exec` output-budget directive.

## 12. Ordinary delegation in the shared review budget

New defaults pin `ordinary_contract=frozen-v3-four-tier/1` alongside transport `/2`.
Existing roots without that opt-in retain their semantics. Worker/Explorer use only
GPT-5.6 Luna Low/Medium and Terra Medium/High, with frozen weights 1/2/4/8. Select
one explicit profile; do not inherit the parent model or borrow Reviewer quality
cards. `selection_basis` identifies fixed-policy authority rather than statistical
qualification and never supplies empirical quality or gain evidence.

Ordinary preparation verifies current scoped Evidence, approved prompt, host model
capability and shared capacity. Future pre/post/repair review slots still consume
global, role and phase allowances. Ordinary tasks do not promise wallclock deadlines.
Dispatch text must equal the approved prompt. Independent forks, native parent/child
identity, unique permits and creation receipts remain mandatory. Tools stay isolated
until the receipt arrives; verified ordinary tasks then use normal tools within their
original scope and host permissions. Reviewer fixed-reader and logical-readonly
restrictions do not apply to Worker/Explorer tasks.

Ordinary completion has separate native text proof and `ORDINARY_RESULT_ACCEPTED`;
it does not require review JSON. Native completion does not satisfy the task by
itself. The parent must provide current repository/project/task validation Evidence
from `parent-ordinary-task-validation`, scoped to `ordinary-reservation:<reference>`
and `ordinary-verdict:pass|incomplete`. A known failed, cancelled, partial or blocked
host outcome cannot become pass. Incomplete work retains cost and history. Retries
need new evidence, reference the prior result and supersede exactly the unresolved
results. Replayed events do not charge twice. Ordinary results never enter Reviewer
state, qualification grading or qualification traces. New default preparation also
verifies that the installed payload contains this ordinary contract.

Internal `ordinary-prepare` and `ordinary-result` controls are not a standalone CLI
product. Production roots still require complete Reviewer statistical qualification,
valid project activation and installed-content readback. Ordinary compatibility tests
do not grant model qualification or bypass default-migration gates.

## 13. Independent phase evaluation

A new transport `/2` evaluation root may explicitly pin
`evaluation_contract=isolated-review-phases/1`. This contract is EVALUATION-only:
all slots must use registered Reviewers, condition=always and no workflow
dependencies. Ordinary roles, production roots, legacy transport and real repair
dependency slots cannot opt in. Unflagged roots still require a real blocking post
result before the first repair dispatch. Production repair gates retain their meaning.

The evaluation measures how a model reviews frozen pre/post/repair material. A
repair case must supply the original issue, previous report, repair candidate and
validation material in the approved prompt. A phase marker never replaces source
or gold review. Independent cases do not create production blocking results,
supersede real earlier reviews or certify live workflow transitions. Requests,
receipts, material, native final text, complete grading denominators and spending
retain the native evidence chain. Controller accounting or synthetic transcripts
cannot substitute for model provenance. This contract changes neither statistical
gates nor segment/aggregate capacity. Defaults still require complete statistical
qualification and production workflow acceptance. Internal init accepts the explicit
--evaluation-contract option.

## 14. Integrated results and case applicability (not wired to dispatch)

`review-vector/1` fixes seven dimensions. The model supplies per-dimension verdicts,
findings, checked scope, unverified items and summaries. The controller owns the
complete applicability scope: applicable, not-applicable or unknown. Determined
applicability needs Evidence references. Structural validation does not prove that
those sources were actually verified. The model cannot dismiss required or unknown
dimensions as not-applicable. Unknown dimensions must be incomplete; unresolved
dependencies cannot produce completed verdicts. An entirely inapplicable vector
remains incomplete rather than passing automatically.

The controller aggregates `validated-review-vector/1`, retains known blocking
findings, and reports missing evidence as incomplete. Existing semantic expansion
supplies fixed governance fields. The seven dimensions share a 64-finding limit and
a 1MiB response bound. Conflicting IDs, missing/unknown dimensions and model-injected
cost or receipt fields are rejected.

`review-dimension-view/1` is a display/scoring view of one result, with a shared
vector_ref, model payload and scope reference. It is not an independent call,
native receipt, legacy Result or qualified sample. Old consumers reject the vector
envelope. One call cannot become seven charges or seven independent problems.

The case matrix aggregates applicable clean/defect/critical labels by phase,
dimension and independent cluster. Unknown or inapplicable rows do not fill
denominators. Problem/root-cause aliases across clusters are rejected; conflicting
variant labels require selection before freezing. Output reports coverage gaps,
not formal admission or qualification.

Explicit `review_contract=integrated-review-development/1` is restricted to transport/2
EVALUATION roots and cannot combine with the ordinary delegation contract. A registered
Reviewer is only the development dispatch identity, not a released integrated role.
`integrated-review-input/1` puts phase, instructions, scope and hashed materials in the
self-contained business_prompt; its preregistered digest covers every input. Scope
references must resolve to delivered material bytes; this does not establish independent
gold admission. The model returns all seven dimensions. Hooks bind the native answer;
the controller creates Result 8 with the development contract and full input reference
(including scope), accepting one result against one dispatch charge. Failure accounting
uses that frozen identity even when material later becomes unavailable. The original vector remains content
addressed. Unknown scope is incomplete, confirmed blockers remain, and cancellations or
controller failure accounting cannot become passes. Legacy Result 7, ordinary delegation
and existing budget limits retain their meaning.

This path supports development bridging for all three phases, never formal qualification.
Legacy trace/grading consumers and production root initialization explicitly reject it.
The integrated role, formal comparison/qualification consumer and capacity extension still
require implementation and acceptance. Never copy a development result into seven legacy
Reviewer samples or use it to install/activate a production default.


## 12. Bounded research succession seed (native acceptance pending)

`bootstrap-code-review/1` accepts explicitly authorized code reviews through a distinct
`bootstrap-review-plan/1`, material manifest and stage grant. It has no statistical gold,
clean or critical labels. It reuses EVALUATION budget transport; statistical grading and
trace export explicitly reject this type. Legacy roots, intents, sealed results and costs
remain immutable. This seed neither publishes qualification nor activates production defaults.

Stage approval is consumed once. At most two prepaid segments contain at most four calls
each; immutable claims permanently allocate their capacity. References flow from plan to
manifest, grant, admission, claim/transition and head without ancestor backfilling.
`request_ref` is the exact V5 request with only controller-derived `expected` set to an empty
object; all business fields remain bound and the selector still verifies the live snapshot.
Cost sources bind ancestor material references, never the self-containing plan hash.
Expired/revoked authority permits consumed metadata recovery only, never new dispatch.

Lock order is session, stage, ExpectedSpawn, budget. Before spawn is allowed, persist the
unique native task path/role/depth, host call and reservation indices. Start resolves an
authenticated transcript header even before POST and without a parent call ID. POST uses
a fixed call index; late events retain their original segment. Index persistence failure
keeps the budget facts and denies replay without speculative refunds or creation receipts.

This is a bounded bootstrap. Whole study/2, research campaigns and formal statistical
consumption are not connected yet. Synthetic tests do not prove native Desktop acceptance
or system isolation; formal research remains gated on native code review.


## 13. Explicit same-call notify delivery

`delivery_contract=same-call-notify/1` requires MODE_V2 and the 64KB profile. It does not combine with ordinary_contract or review_contract. Historical single-output programs and proofs keep their original meaning.
One existing reader produces complete raw output; the same fixed Code Mode program emits at most eight parts, each complete UTF8 notification payload below28000bytes. The full material scope and64000byte business limit remain unchanged. Ordinary completion may arrive first and notify is not a Promise; await or sleeps never establish completion. Verify each real top-level metadata budget, same-call membership, order/count/offset/hash, separate complete marker, small summary and final ordering; missing or insufficient evidence fails closed.
Reader facts and cumulative CONTEXT_NOTIFY_ATTESTED are sealed separately. The final model response returns the complete receipt, which is a checksum rather than evidence of reading. Statistical grading re-verifies the full desktop-tool-surface/2 set and its raw/final binding; an old raw receipt alone cannot qualify.


## Explicit trusted wire notifications and spawn-intent metadata recovery

`same-call-notify/2` retains the MODE_V2, bounded-review-64k/1 and evaluation combinations of `/1`, rejecting ordinary/review_contract combinations. Unmarked and `/1` history retain their interpretation; transport grants no production/default/model qualification. The Python controller constructs original part/completion objects; the fixed reader verifies raw/wire digests and reassembly. The short program forwards JSON.stringify frames and the summary, without model-transcribed SHA code. Limits remain bundle 64000, raw 65536, wire 196608 and grant 524288 bytes, with the existing 50000 inner output budget, one Code Mode call/reader/reservation and bounded retries. Exact PROGRAM, the full notification set, actual per-item host budgets and completion/final order remain mandatory.

One new `CONTEXT_WIRE_DELIVERED` event derives both the raw compatibility projection and wire binding; old delivery events cannot establish `/2`. `desktop-tool-surface/3` rechecks the original transcript and grant. Unknown versions, wrong digests/calls, field or size drift are rejected; old failures are not regraded.

`research_seed.recover_spawn_intent` restores metadata for the original admitted stage only: no spawn, refund or new reader authority. Original parent records bind the sessions path, device/inode/header and complete-line offset/length/hash. Later appends are allowed; bound-range rewrites, truncation and file replacement are rejected. Created requires the actual spawn call/result and matching original child header; the original index/identity/receipt are completed idempotently. Created without a reservation is rejected. Start alone, missing results, generic errors and absent trusted negative proof remain UNKNOWN/RECOVERY_REQUIRED. This host has no verified not-started result shape; errors never release capacity. Closed journals are not reopened. Evidence proves logical provenance, not OS isolation or protection against administrator rewriting.
