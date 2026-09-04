# V7.4.5 Validation Report

Status: local validation complete; remote delivery awaits readback.

## Passed

- Official version gate: GitHub stable Release and npm `latest` both report 0.153.3, while the repository's previous public release still declared 0.153.2.
- Native Windows CLI: the same global npm path was updated from 0.153.2 to 0.153.3; version, help, login, and Plugin-list readback pass.
- Compatibility registry: eleven stable releases anchored at 0.153.3, with fail-closed behavior for future, prerelease, and out-of-window versions.
- Isolated 0.153.3 cell: official artifact SHA-256, CLI contract, Plugin round-trip, and synthetic Hook pass.
- Account Plugin: V7.4.5 transactional installation, `HOST_COMPATIBLE`, installed/enabled readback, and three-way 182-file payload identity pass.

## Not pre-claimed by this report

- Ubuntu and the complete eleven-version matrix run independently in remote CI.
- The tag, Draft, six assets, GitHub provenance, and public Release require post-push readback.
- Actual uninstall/rollback and a parent/child Agent lifecycle journey were not exercised.
