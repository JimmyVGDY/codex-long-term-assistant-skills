# V7.5.0 Validation Report

The frozen local release passed complete validation on 2026-09-06: 276 package + 6 runtime. Package validation includes semantic, privacy, routing, payload identity and worktree side-effect gates. Bilingual coverage and link checks reported zero findings.

New acceptance covers task feedback and terminal merging, normal and linked-worktree identity, observer health, incremental concurrency/crash recovery and signal changes, scenario statistics across ledgers, exclusion of implementation tasks from benefit cohorts, insufficient/supported/regressed benefit boundaries, root-cause candidates and rejection of tampered followups.

Two post-implementation logical-readonly review rounds completed. Six accepted findings were repaired and rechecked; the one-immutable-final-report contract was clarified and accepted. No operating-system readonly isolation attestation or activated host DelegationBudget reservation gate is claimed.

The Windows account Plugin was installed as 7.5.0. Codex CLI 0.153.4 version, enabled state and payload readback passed. Installed wrappers and Hooks passed UserPromptSubmit → validate-task → finalize-task → Stop binding and opt-in incremental analysis after SessionEnd sealing in an isolated project. This is not a complete live LLM parent/child Agent host journey.

Plugin payload: 192 files, SHA-256 `11742fa17f56a3f241cbb6bb2a83c3bc7acde11ae74403841ab41769fc269eba`.

See [PACKAGE_VALIDATION.json](PACKAGE_VALIDATION.json) for package evidence. Actual project benefits still require an independent implementation task and a valid observation window of at least seven days with at least five independent tasks per cohort. This release makes no claim of proven real-project benefit. Automation is off by default and proposals permanently retain `execution_authorization=NONE`.

This report records pre-commit local evidence. Remote commits, the Windows/Ubuntu eleven-version compatibility matrix, CI, tag, public Release, ZIP checksums and build provenance must be read from the corresponding workflow and release assets; no success is claimed in advance. Actual account uninstall/rollback was not exercised; the installer transaction backup was retained.
