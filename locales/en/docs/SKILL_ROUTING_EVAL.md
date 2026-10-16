# Skill Routing Regression Tests

## Purpose

Verify that the main agent follows “one primary domain Skill, minimum supporting Skills, phase-delayed activation,” preventing overloading or incorrect routing after new Skills are added.

## Files

- Cases: `tests/skill-routing-cases.json`
- Tool: `scripts/routing-eval.py`

Each case contains:

- `required`: must activate;
- `optional`: activate only when actual project content requires it;
- `forbidden`: must not activate for the current request;
- `max_active`: maximum active Skill count.

The current cases include positive cross-task value, cost-calibration and proposal-governance scenarios, plus negative ordinary repair, independent-review and long-task cases. Counts come from the case file.

## Phase Observations and Exceptions

`phases` is an optional schema-1 extension. Each phase defines its own `id`, `required/optional/forbidden` and `max_active`. Observations record per-phase `activated` and `exception_reason`; top-level `activated` is their union, not simultaneous loading. Missing/duplicate phases, inconsistent unions and phase-contract violations cannot pass.

More than three capabilities in one phase needs a non-empty justification while respecting that phase's maximum and forbidden set. Legacy unphased cases remain readable; an observation activating more than three also needs `exception_reason`. Raising `max_active` alone is not an exemption.

Real-host observations remain schema 2. In addition to existing markers, phased final reports include one `PHASE_OBSERVATIONS=<JSON array>` line; an unphased excess uses `ACTIVATION_EXCEPTION_REASON=<single-line reason>`. The evaluator binds these fields to report bytes and their digest, preventing a justification from being added after capture. This validates host final reports, not an independent routing trace.

## Execution

```bash
python3 scripts/routing-eval.py validate
python3 scripts/routing-eval.py list
python3 scripts/routing-eval.py make-template --output routing-observations.json
```

Send each prompt in a real Codex session and record actual activated Skills under `activated`. Do not inspect expectations and fill them manually.

```bash
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

## Passing Criteria

- every required Skill appears;
- no forbidden Skill appears;
- active count does not exceed `max_active`;
- optional Skills are not mandatory for passing.

## Limitation

Visibility of implicit Skill activation depends on the client. When it cannot be observed directly, ask the main agent in test mode to report only its activation plan without executing the task. This remains model output and does not replace sampling actual behavior.

## Isolation and Model-Routing Cases

The routing set adds:

- strict read-only review: must load `multi-agent-independent-review` and inspect parent permissions first;
- logically read-only review under a writable parent: must state `logical-readonly` and not treat TOML as system isolation.

New defaults use script-selected GPT-6 Luna, Sol and Astra at low/medium/high: Luna/low for mechanical work and Sol/medium for ordinary or unknown work. Multiple Skills do not automatically increase effort. Historical combinations remain only for old-record replay.

Routing tests validate Skill, approved dispatch profile and plan selection. They do not prove sandbox isolation. Actual host model identity is not an Agent input, evidence item or acceptance target.

## Separate development and final sets

tests/skill-routing-study-cases.json and scripts/routing_study.py add a separate study while preserving the original 52 cases, observation formats and scoring rules. Four groups cover documents, design, browsers and MCP, with three positives and three nearby negatives each. Sixteen development cases and eight final cases keep intent families within one split. Critical cases repeat three times: this suite prepares 40 trials per version, 80 overall; read the actual count from preparation.

Run preparation in the Plugin source repository; cases still execute through Codex Desktop. These are internal management and validation tools, not a standalone CLI product track.

~~~text
python scripts/routing-eval.py prepare-study --baseline v7.16.2 --environment <environment.json> --output <new-external-directory>
~~~

environment.json fixes six fields: platform, runtime, requested_model, requested_effort, permissions_digest and cache_condition. Record the environment and requested parameters actually used. permissions_digest is the canonical SHA-256 of the explicitly authorized boundary, not evidence of system isolation. Use --locale en for English cases and English Skill entry snapshots. Preparation neither invokes models nor grants dispatch, file or production authority. Check task budgets and permissions before execution.

study.json freezes the suite, both versions' Skill entry digests, environment, repeats and each input. Requests under prompts contain only opaque trial IDs and original questions, without expected Skills. Executors must not read suite.json, study.json, the other version's artifacts or answer fields. Directory separation is logical isolation, not a sandbox. The candidate defaults to the working tree; --candidate pins a commit.

Record one existing schema 2 host report per trial. New studies accept only codex_desktop_task; the old CLI source remains readable solely for historical records. Original reports additionally need unique TRIAL_ID and INPUT_SHA256 markers. Host readback needs RULE_DIGEST and ENVIRONMENT_DIGEST matching the frozen inputs, rules and environment. Record real task IDs and do not count one task's replay as an independent sample.

Use a separate index for each split:

~~~json
{"schema":"routing-study-results/1","study_digest":"<study.json record_digest>","runs":[{"trial_id":"<opaque trial ID>","results_file":"runs/example/result.json","evidence_dir":"runs/example/evidence"}]}
~~~

~~~text
python scripts/routing-eval.py evaluate-study --study <study.json> --results <development-index.json> --split development --output <new-report.json>
python scripts/routing-eval.py evaluate-study --study <study.json> --results <final-index.json> --split final --output <another-new-report.json>
~~~

Scoring reuses the old host contract and reports missed triggers, false activation, overload and phase errors by version and group. Missing observations produce PARTIAL; actual errors produce FAILED. The command preserves its report and exits nonzero in both cases. Evidence reads have file, total-byte, path and link bounds.

Do not repeatedly tune against final cases. Rebuild a leaked final set or one used to select descriptions, preserving earlier results. The tool never edits descriptions or promotes small-sample counts into benefit claims. Unknown traces, actual fees and UNKNOWN benefit remain explicit. Host final self-reports are not independently signed router traces.
