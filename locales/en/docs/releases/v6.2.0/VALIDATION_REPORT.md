# V6.2 Validation Report

Validation date: 2026-08-28

Target host: native Windows Codex CLI 0.150.1

Python: 3.13.15

## Conclusion

V6.2 source, installation transaction, Plugin registration, V6.1 upgrade recovery, Windows long-path compatibility, and governance safety boundaries passed validation and can produce a formal release package.

## Static and Automated Validation

- Semantic validation: passed; ten Skills, Plugin and Hooks, account Skill directory, model ceiling, and controlled-evolution boundaries agree.
- Neutral-language gate: natural-language files contain no concrete personal name, first/second-person conversation subject, or machine-identity path; machine contracts remain unchanged.
- Routing cases: 35/35 passed.
- Unit and regression tests: 27/27 passed.
- Package validation: passed for version 6.2.0, ten Skills, seven Reviewers, six Hooks, and TaskOutcomeEvent 2.0.
- Windows long paths: two consecutive Plugin installs, backup manifests, verification, and two uninstalls restoring original state passed.
- Junction/Reparse Points: overwrite rejection passed.
- External-file protection: uninstall preserved unmanaged AGENTS content, custom Hooks, and hooks.json metadata that existed before or appeared during install. Managed old-version blocks and Hooks were restorable, marker-text collisions were retained, and malformed hooks.json failed closed without overwrite.
- Hooks: UTF-8, Chinese truncation on Stop, cross-platform Windows launcher, and SessionEnd timeout=3 seconds passed.
- Model gate: Luna Low/Medium and Terra Medium/High allowed; Terra xhigh/max, Sol, unknown models, and future Terra names rejected.

## Real Isolated Upgrade on Codex 0.150.1

Completed under independent `HOME`, `USERPROFILE`, and `CODEX_HOME`:

1. Install and verify V6.1 Plugin.
2. Run V6.2 dry-run.
3. Upgrade and run `verify`.
4. Read `codex plugin list --json`.
5. Confirm V6.2 `installed=true`, `enabled=true`, and `version=6.2.0`.
6. Uninstall V6.2 normally and confirm restoration of V6.1 files, state, and registration.
7. Clear the disposable isolated registration.

The upgrade-backup manifest exists and is readable. Before and after the test, SHA-256 for the real account's V6.1 state file and `config.toml` remained unchanged, and the actual Plugin remained V6.1 installed/enabled.

## Security and Data Boundaries

- `execution_authorization=NONE`.
- No automatic modification of Skills, Reviewers, model routing, content outside managed AGENTS blocks, or business repositories.
- No automatic acceptance or execution of Evolution Proposals.
- No automatic commit, push, deploy, restart, or production operation.
- V6.1 historical project context, Events, Snapshots, Assessments, Proposals, and Decisions are neither migrated nor deleted.
- Self-observation aggregation validates both `project_id + repo_fingerprint`; events use and verify a continuous SHA-256 chain.

## Known Note

The historical V6.1 uninstaller does not support extreme long paths. The V6.2 installer can read and restore V6.1 state compatibly. The final cleanup of the disposable long-path test used the V6.2 uninstaller; the formal V6.2 -> V6.1 restore did not use `--force`.
