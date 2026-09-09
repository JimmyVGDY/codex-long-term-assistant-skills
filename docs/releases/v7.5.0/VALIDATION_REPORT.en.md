<!-- Generated from locales/en/docs/releases/v7.5.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.5.0 Validation Report

The first local candidate passed complete validation on 2026-09-06: 276 package + 6 runtime. Package validation includes semantic, privacy, routing, payload identity and worktree side-effect gates. Bilingual coverage and link checks reported zero findings.

New acceptance covers task feedback and terminal merging, normal and linked-worktree identity, observer health, incremental concurrency/crash recovery and signal changes, scenario statistics across ledgers, exclusion of implementation tasks from benefit cohorts, insufficient/supported/regressed benefit boundaries, root-cause candidates and rejection of tampered followups.

Two post-implementation logical-readonly review rounds completed. Six accepted findings were repaired and rechecked; the one-immutable-final-report contract was clarified and accepted. No operating-system readonly isolation attestation or activated host DelegationBudget reservation gate is claimed.

The Windows account Plugin was installed as 7.5.0. Codex CLI 0.153.4 version, enabled state and payload readback passed. Installed wrappers and Hooks passed UserPromptSubmit → validate-task → finalize-task → Stop binding and opt-in incremental analysis after SessionEnd sealing in an isolated project. This is not a complete live LLM parent/child Agent host journey.

Plugin payload: 192 files, SHA-256 `755b0ca8be4b3b137174de9391aad8ab560453ab2ea2de118c30681cd7246b97`.

See [PACKAGE_VALIDATION.json](PACKAGE_VALIDATION.json) for package evidence. Actual project benefits still require an independent implementation task and a valid observation window of at least seven days with at least five independent tasks per cohort. This release makes no claim of proven real-project benefit. Automation is off by default and proposals permanently retain `execution_authorization=NONE`.

This report records pre-commit local evidence. Remote commits, the Windows/Ubuntu eleven-version compatibility matrix, CI, tag, public Release, ZIP checksums and build provenance must be read from the corresponding workflow and release assets; no success is claimed in advance. Actual account uninstall/rollback was not exercised; the installer transaction backup was retained.

Windows CI exposed mixed short-path aliases (such as RUNNER~1) and full paths in relative references. Feedback and regression enumeration now use fixed references beneath checked directories, and project identity uses the canonical name of the verified Profile path. A real Windows short-path regression passed. Post-fix focused tests and installation readback are recorded separately; the first complete package run belongs to the preceding candidate, and final full-suite evidence comes from CI for the fix commit.

The subsequent Windows alias repair passed 44 focused tests, six runtime tests and one additional logical-readonly review (six reviewer dispatches across the complete task). The updated payload was reinstalled and its installed feedback/sealing smoke checks passed.
