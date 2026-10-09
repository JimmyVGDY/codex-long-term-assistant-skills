<!-- Generated from locales/en/docs/releases/v7.15.1/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.15.1 Release Notes

New tasks default to the nine GPT-6 Luna/Sol/Astra low/medium/high profiles. Scripts calculate facts, routing, shared budgets, reservations, required holds and retries; models retain semantic judgment and bounded adjustment proposals. Missing optional evidence uses default or degraded continuation without disabling gates or inventing success. Explicit 5.6 compatibility and historical accounting remain, and the main chat selection stays unchanged.

This release also defines metric semantics, required capability constraints, hold transfers, no-start retries and adjustment lineage. Natural observations use existing journals without extra calls; quality and actual-cost metrics remain unknown without reliable sources.

V7.15.1 fixes the legacy V5 Context Hook incorrectly denying tools for a new G6 child in the same chat. Root ownership is checked first; legacy roots retain their guard.

Native SubagentStop can precede task_complete. With a verified final assistant message, the controller records UNKNOWN while retaining the consumed attempt and planning units. It does not infer PASS or issue a refund; duplicate Stop events are idempotent. The review projection accepts the native final_answer phase.

The installed V7.15.0 cache and original failure evidence remain available. Installation, fresh Desktop validation, commit, push, and public release require separate readbacks.
