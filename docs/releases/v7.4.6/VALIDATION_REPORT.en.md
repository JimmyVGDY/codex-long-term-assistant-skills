# V7.4.6 Validation Report

Status: local validation and logical-readonly independent review complete; remote delivery awaits readback.

## Passed

- Official version gate: GitHub stable Release and npm `latest` both report 0.153.4, while the repository's previous public release still declared 0.153.3.
- Native Windows CLI: the same global npm path was updated from 0.153.3 to 0.153.4; version, help, login, and Plugin-list readback pass.
- Compatibility registry: eleven stable releases anchored at 0.153.4, with fail-closed behavior for future, prerelease, and out-of-window versions.
- Isolated 0.153.4 cell: official artifact SHA-256, CLI contract, Plugin round-trip, and synthetic Hook pass.
- Account Plugin: V7.4.6 transactional installation, `HOST_COMPATIBLE`, installed/enabled readback, and three-way 182-file payload identity pass.
- Focused regression: 51 installer-security and Codex-compatibility tests pass.
- Full package validation: 239 package tests and 6 runtime tests pass; the minimum Python version is 3.11 and the validated runtime is 3.13.15.
- Documentation and delivery gates: 45 release/documentation tests, 43 post-repair focused tests, strict localization with zero findings, semantic lint, repository link checks, and diff checks pass.
- Independent review: logical-readonly; the three evidence-consistency findings from the original two rounds and one additional semantic-gate finding from the recovered pre-release review were repaired centrally, with no blocking finding remaining.

## Not pre-claimed by this report

- Ubuntu and the complete eleven-version matrix run independently in remote CI.
- The tag, Draft, six assets, GitHub provenance, and public Release require post-push readback.
- Actual uninstall/rollback and a parent/child Agent lifecycle journey were not exercised.
