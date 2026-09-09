# V7.7.0 Release Notes

This release restores controlled `apply_patch` writes for explicitly enabled projects while keeping ordinary conversations and projects without an enabled policy independent from gate state.

- Add repository-external Operation v2: the first attempt A only creates an origin and is denied; after preparation, a different attempt B must atomically claim permission.
- Add the canonical PreToolUse/PostToolUse adapter. It trusts only `tool_name=apply_patch`, `tool_input.command`, and the real `tool_use_id`; Edit/Write remain matcher aliases.
- Add `--operation-ref` to `capability-task-prepare/finish/check/cancel`. The CLI cannot create host origins or supply dispatch IDs, while legacy session/turn arguments remain compatible with GateTask v1.
- Completion requires B's matching PostTool receipt, a real in-scope change, complete reuse decisions, index maintenance, and readable external receipts. Policy changes, cancellation after permission, missing receipts, and stale evidence remain `OUTCOME_UNKNOWN`.
- Patch bodies are never persisted in Operations, receipts, or observation logs. Command, target, path, and file-read limits are fixed and tested.
- Bind all eleven frozen Codex stable versions to official PreToolUse/PostToolUse schema plus the successful ApplyPatchToolOutput, PostTool payload, and string-response implementations by tag, commit, path, and SHA-256. Hosts missing any evidence cannot install the static enforcing Hook.

Hook permission and the actual file write are not one cross-process transaction. Shell, MCP, and unknown writers are outside this protocol. Workflow evidence neither approves business semantics nor grants commit, push, publication, deployment, or data-write authority.
