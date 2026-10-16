<!-- Generated from locales/en/docs/operations/gate-recovery-policy.md; edit that source and run scripts/documentation.py sync. -->

# Gate recovery and result reporting

Gates decide whether a specific action can proceed; evidence describes what has been verified. Missing optional material or an audit callback must not automatically stop an entire task, demand repeated approval or require a restart. Continuing does not turn UNKNOWN into PASS.

## Common handling

| Condition | Response |
|---|---|
| Missing noncritical context, historical samples, quality cards or optional checks | Use the existing default or degraded path and record the gap |
| Lock contention, transient reads or a delayed transcript | Recover the original call within bounds; do not launch another paid call |
| Missing audit callback after a write | Read the original Operation and target files; do not replay the write merely to obtain a receipt |
| Native execution settled but host business verdict UNKNOWN | Display settled execution and read business or review evidence separately |
| Changed baseline or expired permit | Reprepare the affected action, retaining earlier failures and charges |
| Confirmed authorization, identity, integrity or budget violation | Restrict the affected action while continuing unrelated authorized work |
| Existing explicit authorization still applies | Reuse it; script preparation and evidence gaps do not themselves require another user confirmation |
| Host permission refusal | Preserve that restriction; plugin scope registration cannot grant host permission |

## Actual entrypoint audit

This work uses v7.16.2 as its baseline and covers the installer's three managed Hooks, twelve policy gates, and workflow, installation and observation controllers. Frozen V3/V4/V5 journals retain their historical interpretation.

| Entrypoint | Audit result and correction |
|---|---|
| cp_gate.py / Operation prepare | Separate repository changes from external task artifacts; retain project identity and actual write admission |
| Paths and index | Ordinary long filenames no longer trigger free-text entropy checks; retain sensitive paths, concrete credential signatures, link and escape checks; allow degraded missing-index use |
| PostTool / Operation finish | Audit gaps request readback rather than a blanket block or a claim that no file exists; identical repeated completion callbacks remain idempotent |
| cp_context.py | Route task scopes to their original roots; callback failure records a context audit gap instead of declaring the whole task incomplete |
| cp_hook.py / budget initialization | Isolate logical tasks; budget routing errors do not block unrelated parent reads or writes |
| Dispatch permits, concurrency, future holds and retries | Reuse atomic reservation and authorized templates; renaming, continuing or switching tasks cannot erase overspending |
| Model choice and context readiness | Missing optional material uses defaults or limited context; no statistical qualification wall or automatic profile escalation |
| Pre-review, post-review and repair review | Missing proof is not a pass; adjudicated defects restrict the corresponding hazardous action |
| Workflow stages, validation and final claims | Unverified stages allow reversible work; read back commit, push, publication, installation and effect separately |
| Installation compatibility and transactions | Missing runtime readback remains unverified; verify package hashes, targets, transaction integrity and required host protocols |
| Same-chat handoff and task completion | Preserve old bytes and unresolved calls; late events return to the original task; require matching readers before publishing the new routing schema |
| Observation health | Damaged data restricts the affected analysis rather than business execution |

Post-merge routine checks can still be running after required pre-merge checks have passed; continue collecting their results. No restart does not mean no effect: verify current components and actual execution first, and discuss a restart only when a changed setting genuinely requires reloading. An UNKNOWN host verdict is not a restart requirement.

Review scope accepts the existing string list and a bounded structured object. Additional descriptive fields remain metadata; only explicit top-level evidence fields such as packet_sha256 and context_sha256 participate in binding. Nested descriptions cannot substitute for proof. Field count, depth, nodes and string length are bounded, and invalid digests remain rejected. Preserve the original report; do not redispatch unchanged, source-bound passing material merely because it contains outside-scope uncertainties or additional descriptive fields.

The original journal is authoritative for allowance approval. allowance-recover and allowance-status remove stale pending-question views after a request is resolved and return the next step for the original call or existing allowance. Questions, approvals, revocations and charges remain recorded; refreshing status grants no new authority.

Windows ordinary and namespace paths identify the same native source only when filesystem checks prove the same entity and canonical-path, file-identity and header digests agree. Preserve historical path spelling, task references and approvals. A proven alias does not demand renewed authorization; actual file replacement remains rejected. Source diagnostics expose only bounded contract codes or exception types.

## Missing native completion callbacks

When a child has finished but SubagentStop is missing, run `review_controller.py reconcile --review-dir <original-directory>` on the original controller. Admission also performs bounded readback. Recovery reads only host transcripts of children registered to that root, checking identity, project, header digest, creation receipt, reservation time and an unambiguous turn. An explicit native terminal event is required; a final answer alone is insufficient.

Readback settlement retains charges, attempts and task ownership. Business outcome may remain UNKNOWN, while cancellation remains CANCELLED. The evidence identifies native transcript readback rather than claiming that SubagentStop occurred. Repeated reconciliation and late callbacks cannot rewrite a recorded terminal. Identity conflicts, ambiguous turns, missing records or insufficient bounded reads retain the reservation while unrelated work can continue; never manually release quota or invent a callback.

When the creation receipt is also missing, the coordinator can provide up to two candidate sources with `--child-transcript <actual-native-child-file>` on the original controller's reconcile command. A path only locates a record; recovery still checks the native parent, task name, role, project, original reservation and header timestamp. It does not invent SubagentStart, context delivery or business PASS.

Review receipts freeze minimal metadata before terminal settlement and are published only when the actual journal terminal exactly matches the frozen proof. Staging contains report digests and source references, not answer bodies. The same reconciliation entrypoint can retry publication after settlement without new charges or replacing the original report with later appended answers. Conflicting proof still rejects that receipt.

## Write receipt boundaries

A pre-write denial means that invocation has not executed. A post-write audit failure does not prove the files are unchanged. Read back the files, original call and subsequent validation, then report file results separately from audit completeness. A real identity or command conflict still restricts confirmation of that result. Never synthesize native callbacks, loosen the filesystem sandbox or reuse admission for a different patch.

Operation deadlines distinguish current permits from expired evidence; expiry does not undo a completed file change. Missing receipts remain UNKNOWN without permanently freezing subsequent safe work. A new version does not retrospectively relabel historical audit gaps as PASS.

## Validation and acceptance

[Policy gate tests](../../tests/test_g6_all_gates.py), [actual entrypoint tests](../../tests/test_desktop_gate_controllers.py), [write-gate regressions](../../runtime/tests/test_desktop_gate_repair.py), and [task-scope regressions](../../tests/test_g6_task_scope.py) cover different boundaries. Read installer and account registrations rather than proving completeness only by iterating a static catalog.

Record tests, independent review, candidate installation and real Desktop acceptance separately. This document does not replace a release acceptance report.
