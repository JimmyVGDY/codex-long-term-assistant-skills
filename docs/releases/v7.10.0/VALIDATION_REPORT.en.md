<!-- Generated from locales/en/docs/releases/v7.10.0/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.10.0 Validation Report

This report records validation of code candidate e54158fd88da4a64000da78e9e40846893b58b7a on 2026-09-15. Release, provenance, public downloads, and Pages are separately established by workflows and readbacks for their actual target commits.

Full local package validation passed: 480 package tests and 231 runtime tests. Focused suites passed: 41 diagnostics, 8 benchmark, 26 recovery/resource, and 76 delivery-status contract tests. Ubuntu CI covers link cases skipped for Windows privileges. All four Windows/Ubuntu × Python 3.11/3.13 validation jobs and the bilingual build passed. [Candidate CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34932132143), [11-version compatibility matrix](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34932132285).

Counterexamples cover healthy base installation, disabled/unknown/duplicate registration, unavailable required controls, transaction priority, changing reads/journals, oversized/corrupt records, identity conflicts, dirty-content drift, never executing text converters, byte invariance, and process cleanup. Complete STALE queries return 0 through both entries while retaining stale-evidence warnings; partial/unknown queries return 1 and argument/identity failures return 2. Actual POSIX launcher checks cover invalid explicit and valid interpreters plus help without Python.

Bilingual source/projection, strict localization, internal links, and strict MkDocs builds passed. Independent logical-readonly review and bounded repair checks have no remaining code blockers. Installation, registration, fresh-process loading, and business effectiveness remain separate evidence layers.

Real-task comparison uses public fixtures and the same approved profile, three samples per scenario/version. Medians include successful samples only; incomplete samples remain preserved:

| Scenario | Baseline success | Candidate success | Baseline/candidate median seconds | Baseline/candidate median tools |
|---|---:|---:|---:|---:|
| Local fix | 2/3 | 3/3 | 108.9 / 163.0 | 8 / 14 |
| Feature change | 2/3 | 3/3 | 186.7 / 116.1 | 15.5 / 15 |
| Readonly recovery | 2/3 | 3/3 | 149.3 / 148.5 | 16 / 16 |

These are descriptive observations, not general speed or tool-cost claims. Auxiliary-read characters and natural-language clarifications are UNKNOWN. The initial recovery harness added an extra code-repair goal; that scenario was resampled against the plan's readonly goal, retaining the expanded trials outside this table. Local-fix/feature samples come from 1174e2d; subsequent POSIX, recovery-exit, and report changes do not change those Windows paths. Recovery samples come from e54158f.

Deterministic status, doctor, and equivalent recovery flows each completed 20 samples per version. Recovery uses one explicit CLI process instead of three, while observed median time increased from about 1.60 s to 2.39 s; bounded collection and stability checks are part of the new flow. Fewer calls do not establish lower elapsed time. Each repaired-candidate command also passed 20 alternating direct/wrapper pairs: median/p95 overhead within max(200 ms, 20% of the direct backend), equivalent output, and unchanged fixture/context bytes.

Native isolated installation passed base → enhancement → base restoration, 7.9.2 → target, downgrade refusal, and interruption → diagnosis → explicit recovery, preserving unknown files. The actual base cache contains ten Skills and zero package Hooks, with no Python prerequisite for base installation. Fake-host fault tests, native installation, and real-model tasks have separate records.

Native Codex 0.154.0 model acceptance uses private app-server in-memory token authentication without copying or persisting account credentials. This does not validate every host or ordinary codex exec authentication. The actual account was not upgraded and Desktop was not restarted; isolated CLI results do not prove current Desktop or business-project effectiveness.

Evaluate RELEASE_COMPLETE and INCIDENT_EFFECTIVE separately: release/post-publication completion versus additionally proven effectiveness in a specific incident. Package and isolated evidence do not substitute for other required readbacks.
