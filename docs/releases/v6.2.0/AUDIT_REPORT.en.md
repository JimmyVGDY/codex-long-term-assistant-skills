# V6.2 Release Audit Report

Audit date: 2026-08-28

## Scope

- Whether V6.1 field repairs were fully incorporated into V6.2 rather than only changing the version number.
- Native Windows Codex 0.150.1 Plugin and Marketplace registration.
- Installation, backup, rollback, uninstall, protection of unknown external files, and long-path behavior.
- Ten Skills, seven Reviewers, six Hooks, and TaskOutcomeEvent V2.
- Model-cost ceiling, self-observation isolation, and controlled-evolution authorization boundaries.
- Neutral natural language and compatibility boundaries for machine contracts.

## Conclusion

Passed. V6.2 formalizes the V6.1 field repairs and adds Windows extended-length path support with regression tests. A real isolated environment completed the V6.1 -> V6.2 -> V6.1 closed loop, and Codex CLI readback confirmed the target Plugin's installation, enabled state, and version.

Natural-language content uses neutral wording and test identities use anonymous placeholders. Machine contracts such as `--scope user`, JSON field names, and path variables remain unchanged for compatibility.

## Key Assertions

- Plugin ID: `codex-cross-project-engineering-assistant@cp-assistant-local`.
- Marketplace: `cp-assistant-local`.
- V6.2 success requires `installed=true`, `enabled=true`, and `version=6.2.0`.
- Automatic subagents allow only four Luna/Terra tiers with a maximum of `gpt-5.6-terra + high`.
- Reviewer TOML does not fix models; this package does not override the main-agent model.
- SessionEnd timeout is three seconds; Windows Hooks do not require `python3.exe`.
- Proposal always keeps `execution_authorization=NONE`; human ACCEPT is not execution authorization.
- Installation failure rolls back the managed-target list. Uninstall merges and restores managed AGENTS and standalone Hook content without deleting unknown account Skills, Agents, Hooks, MCP configuration, other configuration, or historical observations.

## Evidence Index

- `VALIDATION_REPORT_V6.2.md`
- `RELEASE_NOTES_V6.2.md`
- `V6.2_BUILD_INFO.json`
- `tests/test_package_manager_security.py`
- `tests/test_v60_deterministic_observation.py`
- `scripts/package_manager.py`
- `scripts/validate-package.py`
