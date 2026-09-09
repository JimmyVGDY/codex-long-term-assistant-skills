# V7.6.1 Validation Record

Local candidate record, checked on 2026-09-09. This records checks performed before commit. Exact-commit CI, publication, Pages deployment, account installation and fresh-task results are appended to the corresponding GitHub Release after delivery; this record does not establish those outcomes.

| Item | Local result and boundary |
|---|---|
| Documentation sources and facts | 120 catalog records and 99 English projections; idempotence and drift checks passed |
| Links and bilingual coverage | 614 Markdown files and 1011 internal links passed; not every external website was checked |
| First complete-package command | 317 package tests returned 2 failures and 1 skip; failures are preserved and the full command was not rerun locally |
| Repairs | Added the current SECURITY version fact; delegation Hook fixtures isolate gate configuration instead of inheriting account state |
| Focused repair verification | 10 delegation Hook, 14 site and 16 documentation tests passed |
| Final candidate documentation repair | Package version and validation links derive from the manifest; current/historical release classification is checked; 18 documentation and 14 site tests passed |
| Runtime regression | 144 tests passed in 844.701 seconds, run separately from the package tests |
| Release source boundary | 16 focused tests passed; Windows privileges skipped the symlink case, which passed separately under WSL |
| Bilingual build | Bilingual reproducibility and installation regression passed within the first package run; formal artifacts still require rebuilding and verification from a clean commit |
| Directory compatibility | Anchor sets matched across 16 Chinese/English pages for 8 migration mappings; strict site build passed |
| Payload manifest | Integrity verification passed for 217 managed plugin files |
| External state | 927 historical files were archived and individually verified before original cleanup; current Profile, index and gate bindings were preserved |

The index has bounded, partial coverage. Uninspected entries remain pending; this is not a repository-wide semantic review. Configuration enabled does not establish host loading or a current-task workflow PASS. Older results and checks predating version changes do not replace exact-commit release validation.

The release workflow must rerun complete-package validation on Windows/Ubuntu with Python 3.11/3.13 and the 11 frozen stable-host compatibility matrix, then build reproducible Chinese and English packages from the same clean source snapshot. Publication follows successful workflows, artifact verification and provenance readback.

Before public release, candidate commit 9271828 was superseded after finding remaining current-version labels and release catalog classifications. Its unfinished CI/release runs were cancelled; completed evidence retains that original commit and does not establish the corrected candidate.
