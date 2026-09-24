# V7.13.0 validation record

This record covers compatibility support: frozen V3 remains the default, and new models are restricted to explicit evaluation. Code/artifact evidence is separate from native-budget and model qualification. Default activation is not claimed.

| Boundary | Evidence |
|---|---|
| V4 routing, budget, review, evaluation and observation | 111 focused tests passed after the final Astra concurrency fix, using synthetic host/quality fixtures |
| Desktop component adapter | 4 tests passed; a separate local read-only component/registration probe passed |
| Installer diagnostics | 41 UX tests passed |
| Frozen protocols and evidence | 129 affected checks passed after repair, including Matrix Hook, Review Controller, policies and acceptance mapping |
| Localization and Skill entrypoints | Documentation projections, bilingual coverage and 16 modified language-specific entrypoints passed |
| Local full package/runtime | Before the final Astra fix: package 739 passed, 1 skipped; runtime 231 passed. Later affected checks are separate, not an additive new full-suite total |
| Supported Python CI and reproducible artifacts | Behavioral/packaging baseline a7c8f07 passed all seven CI jobs, covering Windows/Ubuntu with Python 3.11/3.13 and bilingual builds. Local standard-zlib archives match CI byte-for-byte. Final publication is verified against its own workflow and provenance |
| Desktop installation | Candidate installation and verify passed with matching source, marketplace and cache digests; this is not native gate effectiveness |
| Native V4 dispatch | Two calls in an existing task and one in an independent fresh task lacked reservations and creation receipts, while lifecycle starts were observed. Configuration is trusted, but the active pre/post-dispatch path remains unaccepted |
| Empirical qualification | A 36-case/72-generation paired study is preregistered. All three unqualified native attempts retain their actual consumption; qualified samples remain zero. Interrupted or missing results are not scored as model-quality failures |
| Commit / Push / Public Release / Effective | Behavioral/packaging baseline committed and pushed to the PR. Public publication requires separate tag, asset and provenance readback. Enforced budgets and GPT-6 production defaults are not effective |

The packaging correction normalizes staged Windows launchers to CRLF; 20 bilingual regressions cover checkout newline variation and unchanged source bytes. Python 3.14 zlib-ng and standard zlib can emit different compressed bytes. Every archive member was compared equal, and two local standard-zlib builds match the complete CI ZIP. Different-compressor archive hashes alone do not prove different source content.

Desktop management queries prove configuration and registration, not active-task native acceptance. Active Desktop and management component digests matched; no diagnostic established the cause of missing pre/post-dispatch callbacks, so the cause remains unknown. Changed non-managed Hooks require normal trust review; trusted hashes and bypass flags cannot fabricate acceptance. No model production qualification, reasoning gains or actual billing is claimed. Compatibility support retains the old default; later default activation still requires these gates.

Baseline evidence: [a7c8f07 CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/35942327785), [candidate PR](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/pull/14).
