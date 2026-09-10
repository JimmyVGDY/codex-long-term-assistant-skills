# V7.8.0 Release Notes

This release makes direct use with conditionally available enhancements an executable contract while preserving V7.6.2 message neutrality, V7.7.0 Operation v2, and the V7.7.1 Codex CLI 0.154.0 compatibility plus disabled-gate PostTool repair.

- Add the exact C01-C25 `capability-registry/1` authority with AUTO/BASIC defaults, prerequisites, persistence, consent, fallback, and risk references.
- Inherit the V7.7.1 frozen window of eleven stable releases from `0.154.0` through `0.150.0`, including the 0.154.0-only `result-v154` profile and canonical registry-digest validation.
- Add repository-external per-capability preferences. Missing state means AUTO with no write. Explicit OFF, maximum level, prerequisites, and LIGHT/STANDARD/STRICT risk remain independent, and no level grants external-action authority.
- Add `onboarding/1` and separate scan jobs with one offer, nonce/revision CAS, explicit renewal, idempotent choices, cancel epochs, lease fencing, a three-attempt takeover ceiling, and late-result rejection.
- Add a scoped-review companion manifest for targets, statically discovered dependencies, configuration, and authority files. Unknown dynamic dependencies are `INCOMPLETE`; scoped PASS never means repository-wide release PASS.
- Check Python 3.11+ before local installer imports. Windows wrappers and Hook launchers test the actual interpreter version.
- Extend `doctor` with overall and per-feature checks, remediation, and strict behavior; add read-only `inventory`; make state-less uninstall dry-run a zero-delete preview while real uninstall still refuses.
- Persist an installer-source classification and apply it lazily after project binding through exact CAS. Legacy gate, GateTask, and Operation evidence never becomes AUTO, FULL, authority, or scan consent.

The first full scan is optional. A decline, no reply, missing Profile/index/Reviewer, unavailable auxiliary storage, or unavailable child agents keeps ordinary work on the current-source BASIC path. A mandatory independent-review gate remains explicitly incomplete when it cannot run.
