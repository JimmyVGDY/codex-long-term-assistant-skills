# Codex Cross-Project Long-Term Engineering Assistant V6.3 Validation Report

## Subject

- Version: 6.3.0
- Target host: native Windows Codex CLI 0.150.1
- Recommended form: account-level Plugin
- Upgrade baselines: V6.1.0 and V6.2.0
- Event contract: TaskOutcomeEvent 2.0
- Automatic subagent ceiling: `gpt-5.6-terra + high`
- Execution authorization: `NONE`

## In-Package Validation

| Item | Result | Evidence Entry |
|---|---|---|
| JSON/TOML parsing and Python compilation | PASS | `scripts/validate-v63.py` |
| Neutral language and structural semantics | PASS | `scripts/semantic-lint.py` |
| Skill routing cases | PASS, 35 | `scripts/routing-eval.py validate` |
| Package unit and regression tests | PASS, 53/53 | `tests/test_*.py` |
| Shared runtime regressions | PASS, 6/6 | `runtime/tests/test_*.py` |
| Installation transactions and fault injection | PASS, targeted | `tests/test_package_manager_security.py` |
| Lifecycle and self-observation quality | PASS, targeted | `tests/test_v60_deterministic_observation.py` |
| Deterministic ZIP and release-evidence contract | PASS, targeted | `tests/test_v63_release_delivery.py` |
| Evolution Proposal safety boundary | PASS, targeted | `tests/test_v51_controlled_evolution.py` |

Every PASS in `validate-v63.py` derives from commands and suites executed in this run. Unexecuted real-host items remain `NOT_EXECUTED`; constants do not substitute for evidence.

## Isolated Real-Machine Upgrade Loop

Completed with real Codex CLI 0.150.1 under a short isolated account path:

```text
V6.1.0 installed/enabled
  -> V6.3.0 install + verify + Plugin list readback
  -> V6.3 uninstall
  -> V6.1.0 installed/enabled restored
```

Result: PASS.

- V6.3 readback: installed=true, enabled=true, version=6.3.0.
- After uninstall: installed=true, enabled=true, version=6.1.0.
- No active transaction journal remained after V6.3 commit.
- The isolated upgrade backup was retained.
- The real account `CODEX_HOME` was not written during this isolated test.

The first isolated attempt used a deep workspace path and was blocked by V6.1's legacy long-path limitation before V6.3 wrote anything. Retesting with a short isolated path passed.

## Independent Review

Preimplementation review identified gates for release evidence, real lifecycle, reproducible ZIP, observation completeness, and Reviewer attribution. Two logically read-only specialist Reviewers covered state/concurrency and test/delivery after implementation.

Major resolved findings:

- per-target journal ownership for install, repository install, and uninstall;
- persistence of Plugin and Marketplace state before uninstall unregistration;
- complete Marketplace staging with expected target hash recorded before replacement;
- lifecycle aggregation by `session_id + task_id`, with cross-session task conflicts entering the evidence gate;
- duplicate event IDs no longer hiding later chain damage;
- stale-lock logic no longer deleting a lock held by a live process based only on age;
- validation counts and PASS states derived from actual output;
- V6.3 release and audit files included in the package;
- release evidence covers content tampering, illegal paths, correct/incorrect HMAC keys, and cross-parent lifecycle ordering errors.

Review was logically read-only. TaskOutcomeEvent readback reported `gpt-5.6-luna`; actual reasoning effort was not supplied by the host and remained unverified.

## Formal Host Acceptance

Formal account acceptance on native Windows Codex CLI 0.150.1: PASS.

- V6.1.0 -> V6.3.0 Plugin transaction upgrade succeeded.
- `codex plugin list --json` readback: installed=true, enabled=true, version=6.3.0.
- Ten Skills, seven Reviewers, and six Hooks were discoverable; Reviewer TOML did not fix a model.
- Main configuration hash was unchanged and every preupgrade account Skill remained.
- Historical project-context file count did not decrease and the upgrade backup remained.
- No active transaction marker remained, and targets were not Junctions, Reparse Points, or symlinks.
- A new read-only acceptance task started a `cp_review_test_delivery` Reviewer.
- Diagnostic observation reported `gpt-5.6-luna`; the main-agent model configuration did not change.
- One session produced TURN_OPENED, SUBAGENT_STARTED, SUBAGENT_STOPPED, TASK_COMPLETED, and SESSION_ENDED.
- Five TaskOutcomeEvent 2.0 records had a continuous hash chain and matching `project_id + repo_fingerprint`.
- SessionEnd completed within the three-second Hook limit; Windows used `cp_hook.cmd` without extra `python3.exe`.

The formal ZIP hash, byte-identical double build, hashes of the host evidence, and tamper verification are bound by an external machine proof. Without a valid machine proof, the artifact must not be called verified.

## Security Boundaries

- `execution_authorization=NONE`.
- No automatic modification of Skills, Reviewers, main-agent models, or business code.
- No automatic acceptance or implementation of Evolution Proposals.
- No automatic commit, push, deployment, restart, or production operation.
- Project aggregation validates both `project_id + repo_fingerprint`.
- Historical Events, Snapshots, Assessments, Proposals, and upgrade backups survive ordinary upgrade and uninstall.
