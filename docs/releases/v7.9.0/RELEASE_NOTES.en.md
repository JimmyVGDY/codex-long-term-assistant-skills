# V7.9.0 Release Notes

Chinese version: [RELEASE_NOTES.md](RELEASE_NOTES.md)

V7.9.0 separates the Plugin into a directly installable base capability and an on-demand enhancement runtime.

- Add a native base-install entry point requiring neither this package's Python runtime nor an API key; the base path loads the ten Skills only.
- Move Hooks, recoverable state, budgets, controlled writes, account tools, global rules, and Reviewers into the enhancement transaction; the base path does not start them.
- Reuse the existing backup, journal, verification, recovery, and drift protections for enhancement installation; isolated regressions cover base-to-enhancement and enhancement-to-base recovery.
- Make `doctor` and `status` report available work, affected capability, cause, and next action by default; `--json` retains the detailed machine contract.
- Keep simple local work serial in the main agent by default, without proactive subagents, repository-wide scans, or long-lived checkpoints. Strict budgets enforce only with a verifiable real-host binding.

This record describes candidate content only. Commit, push, public release, account installation, Desktop loading, and cross-platform host acceptance require their own readback evidence.
