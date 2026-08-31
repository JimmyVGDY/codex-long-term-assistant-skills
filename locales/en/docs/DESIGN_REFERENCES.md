# V5.0 Design References and Implementation Principles

V5.0 extends V4.2 without copying external source text into prompts. It converts official Codex subagent, model, Skill, and configuration capabilities into executable rules, state tools, structured protocols, and regression tests.

## Capability Basis

- Codex subagents: independent contexts, parallel read-intensive work, custom agents, and model/reasoning configuration.
- Codex Skills: route by name and description first, then load complete `SKILL.md` and on-demand references.
- Codex models: Luna for lower-cost bounded work; Terra for daily engineering and complex judgment. Higher reasoning normally increases time and tokens.
- Codex `[agents]`: default subagent model, reasoning effort, concurrent threads, and interrupt-message configuration.
- Requester-confirmed preference: the main agent normally uses Terra; automatic subagents never exceed Terra High.

## Implementation Principles

1. Give agents a short stable global map; load domain rules progressively through Skills.
2. Let the main agent complete simple work; delegate only when independent value exceeds coordination cost.
3. Escalate subagents along `luna-low -> luna-medium -> terra-medium -> terra-high`.
4. Budget people, model, reasoning, context, and rounds together.
5. Expand review packets from summaries while retaining full diffs for evidence checks.
6. Protect identical packets, reviewers, and checkpoint content with idempotency.
7. Record independent context, logical read-only behavior, and system isolation separately.
8. Turn repeatedly failing workflows into scripts, schemas, checkers, and tests rather than expanding global prompts indefinitely.
