# Independent Review Model Selection and Budget

## Scope

The seven registered cp_review roles may use ten combinations. Workers and explorers retain the original four; the main agent uses the user's selected model. High remains the reasoning ceiling. The authority is runtime/cp_runtime/data/dispatch-policy-v3.json; the manifest and documentation are projections.

| Combination | Scheduling proxy units |
|---|---:|
| Luna Low / Medium | 1 / 2 |
| Terra Medium / High | 4 / 8 |
| Sol Low / Medium / High | 10 / 14 / 18 |
| Astra Low / Medium / High | 24 / 32 / 40 |

Units are versioned scheduling weights, not actual prices or a universal quality ranking.

## Start from Luna

Every new assignment starts at the Luna Low baseline of one point. Score once, then dispatch once; do not make preliminary model calls merely to climb a ladder.

Review budget modes add economy 0, balanced 1, or deep 3 points. STRICT execution, the parent's model, file counts, long logs, and elapsed time alone add nothing.

| Supported evidence | Points |
|---|---:|
| Bounded / cross-module / multi-domain semantics | 2 / 4 / 8 |
| Multi-step / concurrent state | 4 / 8 |
| High-impact / critical irreversible boundary | 4 / 14 |
| Confirmed evidence conflict | 6 |
| Prior inconclusive review with matching result and attempt references | 6 |

Take at most one award per dimension. Exclude missing, stale, or context-mismatched evidence first. The same evidence or root cause forms a transitive exclusivity group that earns one award. luna-evidence-v2 jointly enforces group and dimension limits and maximizes total evidence points. Frozen whole-solution tie rules make input order irrelevant. Maximize raw evidence points first, then add the baseline and mode points and cap the result at 40.

Adding evidence cannot lower the budget when existing evidence remains valid, no existing groups merge, and configuration stays fixed. Corrected correlations or invalidated evidence may legitimately lower it. Frozen reviewer-matrix-v2 / luna-evidence-v1 retains the original greedy evaluator; existing ledgers, states, and samples do not migrate automatically.

Choose the highest-proxy-unit affordable combination within the role candidates and explicit quality requirements. Cost order does not establish capability dominance; Astra Low does not automatically satisfy a Sol High requirement. Stop when no permitted combination meets the requirement.

The coordinator assesses the semantic facts against source evidence. Code verifies provenance, freshness, binding, and arithmetic; a model's own risk assertion is not verified evidence.

## Score once and dispatch once

New tasks use execution-state 5, review-state 8, Reviewer Result 5, DelegationBudget 3, and calibration sample 3. The Task Envelope template has its separate schema 4; Review Packet remains schema 3.

1. Bind the project and task envelope to reviewer-matrix-v3 and its digest.
2. Create the shared packet and record INLINE or DELEGATE. INLINE neither dispatches nor charges a model.
3. The root budget command resolves sealed Evidence files and recomputes the score. Submitted totals or provenance assertions are not accepted.
4. Bind the permit to one review state, reviewer, boundary, phase, round, and packet. Preparation does not charge twice.
5. Dispatch an independent context with the explicit model, reasoning_effort, agent_type, and task_name emitted by the controller.
6. The Hook checks the role, genuine root identity, envelope, current source baseline, and permit, then reserves atomically. Another host call cannot reuse that permit.
7. Collect V5 results, merge findings, and repair together. Do not repeat an already clean packet; reassessment after an inconclusive result requires new evidence.

Prefer review_controller.py result-template for new results. V5 packet templates and validation require --review-dir. Unbound V4 templates serve only the legacy protocol.

## Limits and recovery

Ordinary LIGHT / STANDARD / STRICT allowances remain 4 / 16 / 32. An explicit review-extension adds 72 units to STANDARD / STRICT, producing root totals of 88 / 104. Ordinary role and nonpremium aggregate limits do not grow. LIGHT cannot enable the extension.

Sol/Astra share a maximum of two attempts, one concurrent attempt, and one Astra High attempt. Overall review counts and rounds still apply. A no-start refund does not reset V3 attempt counters. Timeouts, missing associations, and lost replies do not prove that an agent never started or completed.

The root ledger alone owns cost accounting. V8 reconcile restores state from authoritative claims and reservations without inventing review output or refunds. V1 remains read-only; V2 retains its frozen writer rules. V7/V4 reviews retain their four-profile semantics. New tasks use the new policy; old tasks do not silently migrate.

## Capability and evidence levels

The base Plugin remains Python-free. Without enhancement, report policy constraints only. An ordinary worker cannot impersonate an unavailable registered premium Reviewer. Broken or missing required budget binding must deny dispatch instead of falling back to basic mode.

Validate requested tuples, installation/registration, Hook behavior, and real host dispatch separately. A read-only TOML declaration does not prove system isolation. Missing host associations remain unverified. Do not collect or request self-reported host model identity.

## Calibration and changes

Compare independent tasks only within the same project, repository, policy digest, cost formula, and declared pair. Never mix old and new cost cohorts. Insufficient data produces NO_CHANGE. Consider adopted/repaired findings, false positives and misses, regression prevention, duration, and cost; finding count alone is not a benefit measure.

Only the coordinator finalizes attribution with result and validation references. Proposals keep execution_authorization=NONE and never change policy or installation automatically. Changes to weights, scoring algorithms, or candidate relationships require new policy/formula versions while preserving old evaluators.

Native lifecycle association uses the exact PreToolUse tool-use claim, PostToolUse agent-ID receipt, and SubagentStart/Stop callbacks within the verified root session. Callbacks may arrive out of order. Unknown response shapes remain unassociated; generic status, timeout, or missing callbacks never prove no-start. V3 refunds require a matching trusted no-start receipt. No native no-create response adapter is enabled until its contract is verified. A local protocol test does not prove host registration or real dispatch.

Use `task_name` to bind a permit when supported. For a native interface without that field, prepend the controller's `native_message_prefix` verbatim to `message`, then append the review task. Use `native_request_parameters`, including `fork_context=false`. The fixed ASCII first line is `CP_REVIEW_DISPATCH/1 <nonce>`, followed by a blank line. The controller generates a random 256-bit nonce; the ledger retains only its SHA-256 reference. The Hook parses this fixed-length header without scanning or retaining the body. Adjacent duplicate headers and missing, unknown, or conflicting references reject. The reference binds the root session, registered role, explicit profile, current baseline, depth, and claimed review slot. Validation and reservation share one lock; no candidate-count matching remains. The same call can replay idempotently before its creation receipt; a different call cannot reuse the permit. PostToolUse joins by the unique tool-call ID.

Return the reference only to the coordinator's current dispatch call, never to plans, review results, or ordinary logs. A lost preparation response cannot reconstruct or guess the reference: retain the unconsumed state and use an explicit named path or a separately defined recovery workflow. A child receives its own reference only after consumption. The native protocol does not positively authenticate the root caller: this is an explicit single-use permit, not system-level caller isolation. Disclosure before consumption remains within the existing logical trust boundary.
