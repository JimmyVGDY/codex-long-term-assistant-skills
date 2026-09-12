# Plugin UX and cost optimization: S0 baseline and layering decision

The V7.9.0 candidate provides a native Python-free base Plugin and an optional account-managed enhancement runtime. Skills have one source and are never installed twice.

The base loads Skills only. Enhancements provide Hooks, recoverable state, budgets, controlled writes, account tools, global rules, and Reviewers. A failed enhancement must stop its controlled operation rather than bypass it through the base path.

The base was verified in an isolated Windows Codex Home. The same isolation completed base installation, enhancement installation and verification, enhancement uninstall, and base restoration. Real cross-platform host acceptance remains separate release evidence.

The candidate keeps legacy V7.8.1 state, backups, OFF preferences, and unknown files. A base launcher refuses to downgrade a managed enhancement; enhancement uninstall restores its known base state.
