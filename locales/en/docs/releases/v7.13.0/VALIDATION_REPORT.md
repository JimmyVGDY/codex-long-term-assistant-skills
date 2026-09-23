# V7.13.0 validation record

Status: implementation candidate; release acceptance is incomplete.

| Boundary | Evidence |
|---|---|
| V4 routing, budget, review, evaluation and observation | 111 focused tests passed after the final Astra concurrency fix, using synthetic host/quality fixtures |
| Desktop component adapter | 4 tests passed; a separate local read-only component/registration probe passed |
| Installer diagnostics | 41 UX tests passed |
| Frozen protocols and evidence | 129 affected checks passed after repair, including Matrix Hook, Review Controller, policies and acceptance mapping |
| Localization and Skill entrypoints | Documentation projections, bilingual coverage and 16 modified language-specific entrypoints passed |
| Local full package/runtime | Before the final Astra fix: package 739 passed, 1 skipped; runtime 231 passed. Later affected checks are separate, not an additive new full-suite total |
| Supported Python CI and reproducible artifacts | Final remote release baseline remains pending |
| Desktop installation | Candidate installation and verify passed with matching source, marketplace and cache digests; this is not native gate effectiveness |
| Native V4 dispatch | The first call returned a model response and lifecycle events but no reservation or creation receipt. Acceptance failed. Configuration reports the pre-dispatch Hook as modified; normal trust review is pending |
| Empirical qualification | A 36-case/72-generation paired study is preregistered. The one unguarded call is retained separately, excluded from qualification, and further dispatch is stopped |
| Commit / Push / Public Release / Effective | Not executed |

The Desktop management query proves configuration and registration facts, not current-task native acceptance. Changed non-managed Hooks require the normal trust flow; trusted hashes and bypass flags must not be used to fabricate acceptance. Native admission and model screening remain incomplete. No production qualification, reasoning gain or actual billing is claimed.
