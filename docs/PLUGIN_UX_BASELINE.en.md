# Plugin UX and cost optimization: S0 baseline and layering decision

Chinese: [S0 baseline and layering decision](PLUGIN_UX_BASELINE.md)

## Decision

The candidate target is **V7.9.0**. It will use one user-facing base Plugin and an optional account-managed enhancement component: the base keeps `codex-cross-project-engineering-assistant`; the enhancement installs runtime, Hooks, and managed account files without a second Skill Plugin. Skills must never be distributed twice.

This is not a two-rule product. The ten Skills retain one source of truth; the enhancement component carries Hooks and runtime dependencies only. Without Python, a Profile, an index, a ledger, or Hooks, an installer can still start ordinary engineering work through the base Plugin. If an installation with Operation v2, a capability gate, or a Required budget loses the enhancement runtime, the corresponding controlled action must stop rather than bypass control through the base path.

## Fixed baseline

| Item | Verified fact |
| --- | --- |
| Public stable baseline | `v7.8.1` / `22d287fbd45e6f5a91d4ea9bf17e83f19f7d403f` |
| Current candidate branch | `codex/plugin-ux-cost-v790` / `7ffd6a2e7792c257ba7c07a5ded9589bd1b65a76` |
| Inherited candidate work | layering contract (`68fb4e3`) and the `doctor --summary` draft (`7ffd6a2`) |
| Current worktree | clean; inherited commits were not rewritten |
| Native installation interface | the live CLI help exposes `codex plugin marketplace add <SOURCE>` and `codex plugin add <PLUGIN@MARKETPLACE>` |

## Representative tasks and measurement

| Task | Current baseline path | Reproducible measurement | Still required in S5 |
| --- | --- | --- | --- |
| Simple local change | main Agent plus current-source BASIC; no index, ledger, or child Agent should be needed | static rules/call chain located; no real-task trace exists yet | loaded rule/reference characters, tools, child Agents, elapsed time |
| Ordinary feature fix | focused validation and risk-selected independent review | `test_doctor_preserves_fields_and_adds_feature_checks_and_remediation`: 0.089 s | validation, review, and repair count in a real repository fix |
| High-risk change | complete installation transaction, Hook/budget, independent review | isolated fake-Codex `install → verify → uninstall`: 19.022 s | Windows/Ubuntu/macOS real CLI, real Hook, strict-budget rejection |

The 19.022 seconds use the test fixture's controlled fake Codex CLI: they prove a repeatable transaction path, **not** real-account first-success time or Desktop loading. Historical traces cannot reliably recover loaded characters, tool calls, wait time, or success rate. S1 starts collecting these fields; S5 freezes the formal 25% threshold on an identical repository snapshot.

## Current component ownership

| Component | Current V7.8.1 ownership | V7.9.0 target ownership | Migration/uninstall invariant |
| --- | --- | --- | --- |
| Ten Skills and entry metadata | primary Plugin payload | base Plugin | exactly one Skill copy; base installs alone |
| Hooks, Python runtime, `cp-runtime.py`, `evolution.py` | primary Plugin payload and account tool directory | enhancement component/enhancement transaction | base does not start them; controlled features fail closed |
| Managed global `AGENTS.md`, seven Reviewers | account installation transaction | enhancement transaction | retain text outside markers, unknown files, and backups |
| Capability gate, Operation v2, budget, preferences, task state | external state and enhancement runtime | unchanged location and owner | legacy state migrates to enhanced; base cannot delete or downgrade it |
| Marketplace, Plugin cache, installation state, journal | `package_manager.py` | existing transaction/recovery mechanisms | each component has its own digest, managed targets, backup label, and uninstall ownership |

## Layering decisions

1. The base Plugin installs through the native Marketplace path and does not run package Python, require an API key, or write a Profile, index, ledger, or Hook.
2. The enhancement component contains no `skills/`; it is installed only when enhancement is selected. The host therefore cannot discover a second same-named Skill.
3. Enhancement installation reuses `package_manager.py` backup, journal, recovery, verification, and drift protection; it does not introduce another transaction engine.
4. A legacy V7.8.1 full installation classifies as `enhanced` on its first V7.9.0 upgrade. Unknown state fields, OFF preferences, history, and backups must remain intact.
5. Default status must answer four questions: available work, affected capability, cause, and one next step. `--json` retains detailed machine-readable output. The current opt-in `doctor --summary` draft does not meet the default-summary requirement and needs compatibility tests before change.

## Rollback and stop condition

An upgrade keeps the complete V7.8.1 backup. A failed base installation removes only its newly created native registration/cache; a failed enhancement uses the existing journal rollback. If the base path can perform a write that an enabled gate, Operation v2, or Required budget should control, stop S1 immediately, restore the previous stable candidate, and do not release V7.9.0.

## S0 status

The native command contract, current full transaction, and the no-duplicate-Skill structure are located. The base Marketplace prototype, legacy upgrade, enhancement uninstall, real Hook, and cross-platform checks remain unproven. The design decision is frozen; S1/S2 isolated evidence remains the implementation gate, and the public installation flow will not be rewritten before that evidence passes.
