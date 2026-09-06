# V7.5 Controlled Evolution Operations

Status: `active`, package V7.5.1. Default and explicit policy entrypoints use `v7.4.3-default-1`. Every proposal retains `execution_authorization=NONE`.

## 1. Task feedback

After project onboarding, UserPromptSubmit supplies `context_root/project_id/session_id/turn_id/task_id/cli_path` when the host provides complete identity. Route validations already required by the engineering task through the following entrypoint; do not add meaningless tests solely for feedback. Replace placeholders with this prompt's actual binding, never the most recent unrelated task.

```text
python scripts/evolution.py validate-task --context-root CONTEXT --project-id PROJECT --session-id SESSION --turn-id TURN --task-id TASK -- python -m unittest tests.test_target
python scripts/evolution.py finalize-task --context-root CONTEXT --project-id PROJECT --session-id SESSION --turn-id TURN --task-id TASK --actor parent:TASK --outcome PASS --failure-category NONE --routing-deviation MATCHED --repair-rounds 0 --evidence feedback/validations/VAL_ID.json
```

Validation retains a command digest, exit code, duration, Git commit and worktree fingerprint, without command/output bodies, prompts or code. Failed commands or changes during validation produce a nonzero CLI exit. The parent confirms outcome, failure category, repair rounds and routing; counts derive from referenced validation evidence. Earlier failed evidence remains available; final feedback references validation on the current matching worktree.

PASS requires valid passing evidence. Missing evidence remains UNKNOWN; never infer success from natural-language answers. Stop verifies report identity, hashes, references and the current worktree. Raw host terminal fields remain unchanged; observation merges the finalized report. Late feedback for an existing task is effective new input. Identical retries are idempotent; conflicting finalization fails.

Failure categories: `NONE/INPUT_CONTRACT/ROUTING/IMPLEMENTATION/VALIDATION/REVIEW/ENVIRONMENT/UNKNOWN`. Routing: `MATCHED/MISSED/UNNECESSARY/WRONG_DOMAIN/UNKNOWN`. Add `--root-cause-id ROOT --root-cause-confirmed` only after the parent confirms the cause.

## 2. Check observation health first

```text
python scripts/evolution.py health --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py run --context-root CONTEXT --project-id PROJECT --dry-run
```

Both run and automatic incremental analysis use the health gate. The low-level observe API preserves historical read compatibility and is not proof that the health gate passed.

| Status | Meaning and response |
| --- | --- |
| READY | Healthy with eligible signals; candidates may be generated |
| HEALTHY_NO_SIGNAL | Healthy with no eligible signal; remain quiet |
| INSUFFICIENT_DATA | Task count, window or required coverage is insufficient |
| IDENTITY_UNAVAILABLE / IDENTITY_MISMATCH | Binding is missing or project/repository differs; stop aggregation |
| DATA_DAMAGED | Invalid profile, data, reference or seal; retain evidence and stop |
| SEAL_PENDING | Wait for the worker to seal the pending tail |
| STALE_DATA | Newest record is over 30 days old by default |

Health includes policy digest, identity, chain integrity, lifecycle, terminal-outcome, reviewer attribution and cost coverage. Each signal uses its own evidence gates. Never recalculate historical hashes, skip bad lines or mix projects to clear a gate.

## 3. Effective increments and project automation

```text
python scripts/evolution.py incremental-run --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation enable --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation tick --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation disable --context-root CONTEXT --project-id PROJECT
```

Automation is off by default. Opt-in permits checks, aggregation and candidate generation, without implementation authority. The existing SessionEnd seal worker triggers enabled projects; no new service is installed. Defaults are three new independent tasks and a 3,600-second cooldown, in addition to the observer's existing sample/window gates. `--milestone VERSION` explicitly triggers milestone analysis. Policy changes and late feedback/calibration samples are also recognized.

NO_CHANGE, WAITING_FOR_TASKS and COOLDOWN remain quiet. Input fingerprints cover policy, record identities/hashes, feedback and calibration. A project lock protects immutable transaction/snapshot publication and candidate registration before an atomic watermark commit. No-change runs still verify existing outputs. Interrupted runs reuse the transaction without consuming the watermark. Worker analysis failures persist RETRY_REQUIRED in `evolution/automation-last-result.json`; a later effective seal or manual tick can retry. Unchanged failures do not repeatedly notify. Notification flags are consumed by callers; runtime sends no external messages.

## 4. Calibration across independent task ledgers

```text
python scripts/evolution.py calibration-source --context-root CONTEXT --project-id PROJECT --ledger calibration/task-a-budget.jsonl --samples calibration/task-a-samples.jsonl
python scripts/evolution.py calibration-replay --context-root CONTEXT --project-id PROJECT
```

Register each task's own ledger and sample file under the same project context. Each sample is checked against its completed reservation, approved profile, cost and parent-finalization evidence. Group by role, responsibility, difficulty, risk and context size. Aggregate within each task before equal task weighting; preserve independent-task counts, conservative intervals and harm rates. Unknown scenarios, insufficient samples or overlapping intervals do not recommend profile changes. Global observation and offline replay share the comparison function. Legacy reviewer-wide proxies remain diagnostics and cannot drive new-project automatic candidates.

## 5. Hypotheses, implementation and benefit

New proposal schema 2.0 freezes baseline snapshot/metric, improvement direction and target, quality guardrails, project/repository/scenario scope, and defaults of five independent tasks and seven observation days. Baseline and follow-up use the same policy with disjoint task cohorts; follow-up starts after implementation validation. Results are observational evidence, not causal proof.

Human `decide --decision accept|reject|defer` requires --proposal-id, --actor and a rationale of at least ten characters. ACCEPT only permits creating a separately authorized implementation task. That task follows the usual envelope, approval, validation and review workflow.

```text
python scripts/evolution.py snapshot --context-root CONTEXT --project-id PROJECT --window-start START_ISO --window-end END_ISO
python scripts/evolution.py observe-benefit --context-root CONTEXT --project-id PROJECT --proposal-id PROPOSAL --actor parent:TASK --before BASELINE_PATH --before-hash BASELINE_HASH --after AFTER_PATH --after-hash AFTER_HASH
python scripts/evolution.py validate --context-root CONTEXT --project-id PROJECT
```

Use link-implementation for the task and Git baseline, then record-validation for the implementation commit and validate-task evidence. Snapshot windows are timezone-aware half-open intervals. The before reference must be the proposal's frozen baseline snapshot. Observe-benefit and lifecycle readback both revalidate references and metrics.

Implementation PASS is separate from benefit SUPPORTED, NOT_SUPPORTED, REGRESSED or INSUFFICIENT. Closing with PASS requires the latest benefit to be SUPPORTED; insufficient evidence continues observation. Cancellation records an explicit proposal cancellation. Rollback requires validation of a clean worktree at the baseline commit. No observation may be appended after a terminal state. Historical schemas retain their existing hashes and lifecycle, without fabricated benefit contracts.

## 6. Regression candidates from failures

Repeated-failure proposals with parent-confirmed causes produce pending negative-test, routing-case or preflight candidates under `evolution/regression-candidates/`, linked to original reports and validation. Candidates contain conditions and expectations; concrete project fixtures require a separately authorized implementation task. Subsequent benefit reports generate regression-followups with recurrence rates and insufficient-data status. Cross-project promotion requires separate review. Runtime never writes business tests, accepts proposals or modifies rules automatically.

One immutable final report is allowed per project/repository/session/turn/task. A workspace change after finalization requires a new turn. Verified signal changes bypass both the new-task threshold and cooldown; damaged or incomplete lifecycle evidence still fails health gates. Benefit cohorts exclude the implementation task. Registry validation replays regression followups against candidate sources, implementation evidence, independent task cohorts and observation windows.
