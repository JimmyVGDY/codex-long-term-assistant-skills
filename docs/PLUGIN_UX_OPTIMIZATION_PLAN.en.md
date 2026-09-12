# Plugin ready-to-use and low-cost optimization plan

Chinese: [Implementation plan](PLUGIN_UX_OPTIMIZATION_PLAN.md)

## Current direction

This work starts from V7.8.1. The base Plugin must install and support ordinary engineering tasks without Plugin-specific Python, Profiles, indexes, ledgers, or Hooks. Enhancements are activated only for long-running tasks, indexing, controlled writes, or enforced budgets.

Base capability never weakens authorization, project validation, or an enabled safety control. Installation, registration, current-task loading, and business acceptance remain separate facts.

## Layer contract

| Component | Contents | Dependencies | User outcome |
| --- | --- | --- | --- |
| base | Ten Skills and user-facing Plugin metadata | Codex Plugin host | Install and describe an engineering task directly |
| enhanced | Hooks, Python runtime, account tools, Reviewers, managed global rules | Python 3.11+ and verified host contract | Long-task memory, indexes, budgets, and controlled writes |
| strict controls | Enabled gates and Required budgets | Equivalent enhanced enforcement | Controlled operations fail closed |

Base and enhanced share one source of engineering rules. The enhancement must not ship duplicate Skills that cause the host to discover the same Skill twice.

## Security and migration decisions

1. When a capability gate, Operation v2, or Required delegation budget is enabled, removing the enhancement is refused. Base mode is never a bypass around write controls.
2. An existing V7.8.1 full Plugin migrates to `enhanced`, preserving state, backups, unknown assets, and explicit OFF preferences.
3. Each component has its own payload digest, managed targets, backup label, and uninstall ownership. Base, enhanced, and unknown assets cannot delete one another.
4. The default `doctor` summary states available work, affected capability, cause, and one next step. `--json` retains machine-readable detail.
5. A host without a verified Hook contract can still use base. Hook-dependent capability reports unavailable rather than fully compatible.

## Delivery order and acceptance

1. Define base/enhanced manifests, state schema, and release-artifact matrix.
2. Adapt installation, verification, inventory, recovery, uninstall, and legacy-state migration.
3. In isolated accounts, validate clean base, base-to-enhanced, legacy full Plugin upgrade, enhancement uninstall, rollback, and interrupted recovery.
4. Apply LIGHT serial defaults, valid-evidence reuse, and human-readable diagnostics.
5. Update bilingual README, installation material, CHANGELOG, and release evidence. Publish only after platform and real-host acceptance.

Minimum safety acceptance: with an enabled gate and no verifiable Operation v2 origin, `apply_patch`, `Edit`, and `Write` remain denied. Base capability may continue only for ordinary work outside that control.

