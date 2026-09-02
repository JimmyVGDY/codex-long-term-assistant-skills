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
