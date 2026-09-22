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

Also sample: Luna for mechanical work, Terra for business judgment, Terra High automatic ceiling, and no reasoning escalation merely because multiple Skills are active.

Routing tests validate Skill and plan selection only. They do not prove the actual subagent model or sandbox; use task evidence, structured results, and isolation records for runtime facts.
