# Desktop gates and recovery

This package supports Codex Desktop only. Gates distinguish permission to continue from verified completion. Missing indexes, review material, or statistical samples produce default or degraded steps. Confirmed identity conflicts, path escapes, damaged ledgers, and exhausted capacity restrict the affected action. Internal management scripts are not a standalone CLI product.

| Actual entrypoint | Responsibility | Missing material or transient failure |
|---|---|---|
| `cp_gate.py` | Native file targets, prestate, operations, and receipts | Preserve the cause and return complete preparation arguments. Stop consuming an unavailable index while independently checking targets and prestate |
| `cp_context.py` | Bound child-context boundaries | Ordinary parent reads do not consult a child budget; frozen restricted children retain their boundaries |
| `cp_hook.py` | Dispatch, continuation, receipts, and minimal observation | Reconcile the original call; preserve attempts and cost state instead of replacing an unknown call |
| `execution_guard.py` | Workflow stages and action evidence | Missing optional material permits reversible work or local delivery without fabricating completed gates |
| `review_packet.py` / `review_controller.py` | Review material and result management | New work uses G6; schema validation does not prove native review or semantic correctness |

Every installer-owned registration must map to the entrypoint inventory. Unknown managed commands cannot be classified as third-party to avoid checking them. Actual third-party account Hooks are explicitly outside package coverage.

## File writes

In-repository absolute paths are normalized before escape, sensitive-path, and reparse-point checks. Original command digests, targets, and prestate remain bound to the native tool-call, session, and turn identities. Aliases cannot override security fields. Inert extension metadata does not independently deny an operation.

With Operation v2 enabled, the first native call creates an origin and returns `prepare_native_operation`. Its `exact_parameters` contain the interpreter, script, and argument array. Prepare the operation, then retry the original patch with a new native invocation. A missing search term is derived from target filenames. Never fabricate host IDs or origins.

The capability index is a locator aid. Partial coverage, absence, or unavailability remains `index_verification=UNVERIFIED`, while actual source, project identity, and file prestate are independently checked. Damaged indexes are neither trusted nor rewritten to manufacture success. Verified file effects do not establish index or business correctness.

## Subagents and budgets

New execution envelopes and review controllers default to GPT-6 Luna, Sol, and Astra at low, medium, and high effort. Unknown work uses Sol/medium. The main agent remains unchanged. LIGHT, STANDARD, and STRICT consume the authorized root's capacity; call arguments cannot expand it.

An idle child's continuation obtains a new permit in the original root and work lineage. A running child is addressed through non-starting `send_message`, avoiding an unreserved turn if it becomes idle after checking. Agent IDs, short names, and canonical paths resolve only through verified identities in the same root.

Long transcripts use bounded complete-line windows. Partial trailing lines and late creation or terminal receipts are reconciled against the same native handle. An old turn cannot settle a new continuation. A damaged reconciliation sidecar does not block other records or erase accounting. Only sourced not-started evidence can adjust a hold under the existing ledger rules; unknown does not mean free.

Planning units are not credits. Budget enforcement is limited to integrated native paths and verified bindings. Without host enforcement or isolation evidence, describe policy constraints or logical-readonly operation, never system-readonly isolation. A successful read task does not prove every write surface is isolated.

## Validation and compatibility

V3/V4/V5 roots replay their frozen policies. Explicit legacy selectors preserve compatibility, without restoring historical qualification prerequisites for new defaults. Source changes, checks, independent reports, commits, pushes, installation, and runtime effects remain separate evidence.

Test installer output and actual registered entrypoints rather than enumerating only the policy catalog. Keep tested gates enabled during Desktop acceptance. Static checks, installed-file equality, and empty Hook output do not independently establish complete runtime operation.

Use the [official OpenAI Hook documentation](https://learn.chatgpt.com/docs/hooks) as the event-contract reference. Transcript formats are not a stable interface, so adapters remain bounded and preserve unknowns.
