# Task budgets within a chat

A budget belongs to a logical task with an independent objective and acceptance boundary. A Desktop chat can contain several tasks; its session ID provides host provenance. Reviewers, Workers and Explorers share their task's root budget. An allowance remains bound to its original root, work item, role and profile.

## Identification and recovery

The coordinator identifies independent objectives without requiring the user to repeat “new task.” Corrections, constraints, repairs, retries, splits, renaming and automatic Goal continuations retain the existing task. Ambiguity means continuation. Semantic classification is a coordinator policy responsibility, not something the script claims to prove.

Before the first delegation or a goal switch, register the stable Task Envelope task_id. Save the returned task_scope and ledger path in the current task checkpoint. Recovery uses these fixed references rather than inferring ownership from the chat's current selection.

These are internal installed-runtime commands. The source development entry is scripts/cp-runtime.py. They neither start a model nor grant file or Git permissions:

~~~text
cp-runtime.py task-scope-origins --session-id <native-session> --repo-path <repo>
cp-runtime.py task-scope-select --session-id <native-session> --repo-path <repo> --task-id <stable-task-id> --origin-ref <TO1-reference> --relation continue
cp-runtime.py task-scope-select --session-id <native-session> --repo-path <repo> --task-id <another-independent-task-id> --origin-ref <another-TO1-reference> --relation independent
cp-runtime.py task-scope-show --session-id <native-session> --repo-path <repo>
~~~

The native parent Hook binds provenance. Only message references, file identity and digests are stored, not prompts. Real user text with images is eligible; automatic Goal injections, tool output and isolated approvals cannot create a new budget. Replaying or renaming one origin reuses its scope. New roots require matching installed readers; uninstalled source must not migrate a live account.

continue prefers an explicitly registered stable task_id; --task-scope can fix the original task. An unmatched name only continues an existing selection, without creating capacity. resume must find a registered task. Use a new stable task_id for an independent objective; the same task_id always reuses its ledger. Finding the same task in another chat requires an explicit handoff that preserves the original root; this version does not recreate its budget automatically.

## Dispatch and callbacks

Preview must carry a fixed scope; a later selection must not decide an earlier call's ownership:

~~~text
cp-runtime.py task-scope-preview --session-id <native-session> --repo-path <repo> --task-scope <TS1-reference> --agent-type worker --task-name <local-name> --message-file <instructions-file>
~~~

Execute the returned exact_tool_parameters. The script generates a scoped subagent name without adding caller-declared budget fields to native tool arguments. PreTool freezes call ownership under the session lock before the existing journal reserves atomically. PostTool resolves the frozen call reference. Creation recovery, Start/Stop, continuations and messages resolve the original root from native headers, receipts and target identity. A late event for A cannot charge B.

Initialize review controllers with the task's --delegation-ledger; subsequent commands validate the original binding. Delayed approvals remain recoverable in that root and cannot move to the chat's later selection. A new task cannot pay for an old task's repairs.

## Completion and migration

~~~text
cp-runtime.py task-scope-complete --session-id <native-session> --repo-path <repo> --task-scope <TS1-reference>
~~~

A task cannot settle while a call is in flight or creation remains unknown. Completion and actual reservation share the session lock. A completed scope also rejects previously prepared but unreserved permits until the original task is explicitly resumed; late Post/Stop settlement remains allowed. Completion preserves the ledger and does not refund capacity. Report settled execution separately from an UNKNOWN host business verdict; UNKNOWN does not automatically mean still running or requiring a restart.

An existing single-task G6 chat can register its entire old root with continue. There is no retrospective splitting, reset or refund. Preserve the old routing pointer and budget history byte-for-byte, retaining historical record versions. After publishing the new routing schema, old readers reject it rather than falling back to a chat-wide budget. Upgrades and rollbacks must retain a reader that supports the new format; do not overwrite it with an incompatible older runtime.

A missing or damaged source, identity or route restricts the affected budget dispatch. Other authorized local work continues. If a first independent objective lacks native provenance, recover that source while continuing feasible existing work. Do not edit ledgers, switch chats or fabricate provenance to obtain capacity.

## Execution allowances and storage capacity

Review allowances remain restricted to the specified Reviewer; Workers and Explorers cannot spend them. Task execution uses a separate task_execution phase in the original task root, bound to scope, role and the exact model/effort. Historical review questions and approvals replay unchanged. Execution questions use question_version=2, showing each allocation's runs, attempt limit and planning units, without claiming actual credit cost.

The internal review_controller.py reuses existing accounting: register with plan --phase post --review-stage task_execution --agents worker or explorer, supplying the actual packet, purpose, model-profile and allowed-path. allowance-quote --additional-dispatches N quotes the current work. Up to three --work-count <work_id>=<count> arguments can combine registered execution plans in one quote. Grants cannot transfer across roles or profiles. Dispatch requires concrete --scope instructions. The packet is coordinator provenance; executors receive assigned inputs, not answer keys or sibling outputs. Execution results do not become Reviewer passes.

The first execution-work registration appends g6-budget-journal/3. Existing /1 and /2 prefixes and charges remain unchanged. Account, cache and caller readers must match before live use. V3 is bounded at 8192 records and 64 MiB, with a 16 KiB maximum per new record. Quoting and subsequent appends reserve record/byte space for remaining attempts, no-start retries and unsettled calls. Insufficient storage prevents an unusable approval question. Legacy prefixes retain their original limits and interpretation; older readers must not read the new journal.

A new source selection is persisted only after task ownership is checked. If another chat owns the proposed task_id, the same source can retry with the correct ID. An interruption after root creation retains the frozen choice; renaming cannot create another budget.

## Validation entrypoints

- [Task scope and late-event tests](../../tests/test_g6_task_scope.py)
- [Native provenance](../../runtime/cp_runtime/g6_task_origin.py)
- [Routing and migration](../../runtime/cp_runtime/g6_task_scope.py)
- [Gate recovery policy](gate-recovery-policy.md)

Isolated native-format tests establish script contracts. Installed readback and real Desktop multi-task acceptance require separate evidence.
