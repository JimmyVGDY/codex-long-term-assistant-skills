# V7.10.0 Validation Report

This report is bound to target version `7.10.0`. Package-only focused and full local validation, target-ZIP isolated installation, and Windows native base/enhancement registration readback are complete; the isolated account has no authentication, so the real Codex task, remote CI, candidate provenance, and public Release readback remain S8/S9 work.

Required boundaries:

- P1-01/P1-02 capability classification, availability, structured actions, and legacy field/exit-code compatibility;
- P1-03 four scenario paths, help, bilingual copy, and unified-entry arguments;
- P2-01 source tree, zh-CN ZIP, English ZIP, no-Python base entry, and legacy-entry compatibility;
- P2-02 Profile/State, legacy Markdown, explicit Evidence, repository changes, budgets, conflicts, and read-only invariance;
- P2-03 deterministic wrapper benchmarks, failure samples, fixture binding, and privacy whitelist.

Confirmed locally: 458 package tests and 212 runtime tests (1 skipped); a 236-file payload with digest `8ee104982604c3e8b81d68530d5607202f255ddbb459a338e5ade36e4e695561`; both target ZIPs have 572 entries, are byte-identical across repeated builds, and passed archive verification. Final ZIP SHA256/size values are kept in the external delivery record to avoid a self-referential release report. The target ZIP completed base installation, enhancement installation, status/verify, and matching `CURRENT` results from installed `cp-runtime.py` and the extracted-package unified entry in a short-path temporary isolation environment; isolated `codex login status` was `NOT_AUTHENTICATED`, so the authenticated real-model task was not run.

The benchmark records 20 paired wrapper-only samples for `simple-local-fix` and `cross-task-resume`. All current samples completed, but the resume wrapper median increased; these measurements cannot claim lower real Agent cost. Real Agent samples, business acceptance, and dynamic host registration remain unverified.

Independent review: two rounds with 3+2 Reviewers; final packet is `60ec3a5a8aa31a7a1cfb6dcdbefc5f5c88c7439d862b312c32bc071be8c46c45`. The conclusion is logical-readonly with nonblocking unverified items; first-round blocking findings were repaired and covered by focused regressions. This repair commit must be rebound to the subsequent delivery evidence.

Verify `RELEASE_COMPLETE` and `INCIDENT_EFFECTIVE` separately. Without a fresh Desktop session or business-project evidence, do not report current loading or business effectiveness. This report is not public-release completion evidence.
