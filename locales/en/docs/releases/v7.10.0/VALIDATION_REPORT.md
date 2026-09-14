# V7.10.0 Validation Report

This report is bound to target version `7.10.0`. Package-only focused and full local validation is complete; remote CI, candidate provenance, isolated installation, fresh-process acceptance, and public Release readback remain S8/S9 work.

Required boundaries:

- P1-01/P1-02 capability classification, availability, structured actions, and legacy field/exit-code compatibility;
- P1-03 four scenario paths, help, bilingual copy, and unified-entry arguments;
- P2-01 source tree, zh-CN ZIP, English ZIP, no-Python base entry, and legacy-entry compatibility;
- P2-02 Profile/State, legacy Markdown, explicit Evidence, repository changes, budgets, conflicts, and read-only invariance;
- P2-03 deterministic wrapper benchmarks, failure samples, fixture binding, and privacy whitelist.

Confirmed locally: 450 package tests and 212 runtime tests (1 skipped); a 236-file payload with digest `8ee104982604c3e8b81d68530d5607202f255ddbb459a338e5ade36e4e695561`; bilingual ZIPs with 572 entries each and byte-identical repeated builds. The zh-CN ZIP SHA256 is `f258466bda79b659bce96a45a1d3bc6fb6bdd89c8e3231139273cdd8809bb2c7`; the English ZIP SHA256 is `adc5217723675d398146e6fcd7f276ecc8b23b77820be418f4db8222d8e8bdc9`.

The benchmark records 20 paired wrapper-only samples for `simple-local-fix` and `cross-task-resume`. All current samples completed, but the resume wrapper median increased; these measurements cannot claim lower real Agent cost. Real Agent samples, business acceptance, and dynamic host registration remain unverified.

Independent review: two rounds with 3+2 Reviewers; current packet is `cad253d578449558b445c0209df9c25f22501486f6983326e0f11d5b10ec9da7`. The conclusion is logical-readonly with nonblocking unverified items; first-round blocking findings were repaired and covered by focused regressions.

Verify `RELEASE_COMPLETE` and `INCIDENT_EFFECTIVE` separately. Without a fresh Desktop session or business-project evidence, do not report current loading or business effectiveness. This report is not public-release completion evidence.
