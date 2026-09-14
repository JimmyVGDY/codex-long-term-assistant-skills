# Plugin ready-to-use and low-cost optimization plan

V7.9.0 is publicly released. This page retains the implementation plan and acceptance targets, not a pending-task list. The final design is one base Plugin plus an account-managed enhancement runtime. See the [release record](releases/v7.9.0/RELEASE_NOTES.md) for publication, account installation, and fresh projectless CLI evidence. Restarted Desktop loading and cross-platform real-host paths still need separate acceptance.

V7.9.0 separates a native base Plugin from optional enhancements without creating two rule systems. The base provides the ten Skills. Enhancements add Hooks, Python runtime, account tools, Reviewers, managed global rules, long-running state, indexing, budgets, and controlled writes.

The base launcher requires neither this package's Python runtime nor an API key. It refuses a managed enhancement downgrade. The enhanced installer reuses the existing transaction, backup, verification, recovery, and drift protections.

Default `doctor` and `status` answer available work, affected capability, cause, and next action. `--json` retains the full machine contract. Simple local work is serial by default; strict budgets enforce only with verifiable host binding, ledger, and permits.
