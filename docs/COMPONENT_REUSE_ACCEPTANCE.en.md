<!-- Generated from locales/en/docs/COMPONENT_REUSE_ACCEPTANCE.md; edit that source and run scripts/documentation.py sync. -->

# Component and Module Reuse Acceptance

This procedure evaluates the [shared reuse rules](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/locales/en/skills/engineering-quality-delivery/references/component-module-reuse.md). It is for package maintainers, not an automatic step in ordinary application tasks.

## Prepare and Execute

Run `scripts/reuse-eval.py prepare --case <case> --output <new external directory>` for the current candidate. Add `--baseline <verified commit>` for historical rules and `--locale en` for English rules. Every run uses a new directory; existing destinations are rejected. `tests/reuse-fixtures.json` contains task inputs; `tests/reuse-oracles.json` holds assertions for the evaluator only.

Give the executing agent only the workspace path, the task goal from `prompt.txt`, and consistent execution/write boundaries. It should discover applicable rules through the workspace's `.agents/skills`. Withhold expected reuse decisions, oracles, earlier results, and other scenarios. Record rule hashes, initial application hashes, requested model/effort, start/end times, and available read/execution counts. Metrics without host evidence remain UNKNOWN. Requested settings are experimental controls, not proof of the actual host model.

Use identical model, effort, task, initial application files, and tool permissions before and after. Repeat key scenarios (direct component reuse and compatible extension) three times each; run others at least once. Follow-ups in the same context are not independent replays. Directory and behavioral boundaries provide logical isolation unless runtime isolation is proven.

After execution, run `scripts/reuse-eval.py verify --output <run directory>`. In a temporary copy it runs original tests and hidden behavioral assertions, verifies tests/rules were not modified, and records application differences. It does not write assertions back into the agent workspace. No network, installation, release, or real business API is needed. Fixtures use installed Python/Node; frontend fixtures are dependency-free ES Module components and do not establish Vue/React or full browser interaction coverage.

## Manual Judgment Matrix

| Case ID | Inspect actual source and evidence |
|---|---|
| direct-component | Settings calls existing action without copying escaping and attribute rules |
| different-name | invoice uses present_minor without reimplementing amount rules |
| similar-different | Strict security codes do not inherit permissive marketing normalization; old marketing behavior stays intact |
| compatible-extension | The same badge supports compact while preserving old calls and default escaping |
| permission-state | Portal filtering always uses the current tenant, without cross-tenant cache or admin-wide access |
| shared-extraction | cart/quote depend on one shipping policy while retaining public entrypoints |
| stale-index | Source confirms the moved safe_name rather than duplicating it from a stale index |
| local-fix | Empty pagination is repaired without shared abstraction or unrelated module changes |

`behavior_passed` covers only fixture behavior assertions and protected-input integrity; `semantic_reuse_review` defaults to UNKNOWN. The evaluator separately inspects call chains, diffs, discovery, and decision evidence, recording discovery, unjustified duplication, incorrect reuse, old-use regressions, and reading/execution cost. The program is not a general semantic reuse judge; executor claims are not independent evidence.

## Gates and Rollout

All candidate cases must satisfy predefined behavioral and semantic expectations, including every key repetition, before independent review and installation acceptance. Preserve failures, attribute them, then revise and rerun affected cases without overwriting failed records. Freeze candidate rules before replay; subsequent rule changes invalidate affected results.

Report package, link, localization, and fixture checks separately. Use existing packet/controller tooling for review without new runtime contracts. After authorized installation, compare actual installed content with candidate hashes and exercise the installed entrypoint in a new host task. Copy-based replay is not installation acceptance; absent installation or new-host evidence remains incomplete. Finite samples do not establish universal reliability, and cases already passing before optimization cannot support a claim of improved reuse rates.

Related: [Capability index](CAPABILITY_INDEX.en.md) · [Acceptance protocol](COMPONENT_REUSE_ACCEPTANCE.en.md) · [V7.6.0 validation](releases/v7.6.0/VALIDATION_REPORT.en.md).
