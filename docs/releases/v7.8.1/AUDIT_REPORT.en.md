<!-- Generated from locales/en/docs/releases/v7.8.1/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.8.1 Audit Record

- Patch root cause: install state intentionally stored the managed global AGENTS block hash, but V7.8.0 inventory compared it with whole-file `tree_sha256`, so a valid installation deterministically appeared as `DRIFT` even though content and authority had not drifted.
- The repair changes only inventory's hash projection and installation-commit readback. User-owned text outside the markers remains independent, while managed-block uniqueness, path containment, and reparse rejection stay fail closed.
- Preimplementation review first found traceability, CAS, lease, cancellation, index-consistency, migration, and scoped-freshness gaps. Functional and state reviewers passed the repaired design, followed by a compatibility refresh against the final R2 merge.
- Registry and onboarding use independent external schemas and locks. They do not modify legacy Profile, Project State, Capability Index, GateTask, or Operation v2 schemas.
- Preferences and capability levels grant no commit, push, release, deployment, production, data-write, or paid-call authority.
- Inventory does not read a state path outside managed roots. Unknown or drifted assets remain untouched, and real state-less uninstall still fails closed.
- Dynamic or unresolved scoped dependencies are `INCOMPLETE`; release audit retains whole-repository freshness.
- Postimplementation source review, cross-process fault injection, Windows/Ubuntu Python 3.11/3.13, public artifacts, and active installation still require separate evidence.
- The initial postimplementation review found missing compensation after a persisted DECLINED response when scan cancellation failed, plus a nonexistent C20 entrypoint and incomplete registry coverage validation. After repair, 419+205 full tests, onboarding 15, registry 10, 30 lock-stress iterations, and an eight-process CAS stress passed; both Reviewers returned PASS.
- Merging V7.7.1 main must preserve the Codex 0.154.0 registry, disabled-gate PostTool repair, compatibility tests, account-loading evidence, and complete history. V7.8.1 reruns affected validation instead of reusing pre-merge counts.
