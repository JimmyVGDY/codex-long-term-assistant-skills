# Codex Subagent Independent Context and Delegation Protocol

## Core Capabilities

- A subagent handles specialized work in an independent context, keeping intermediate exploration and large reads out of the main session.
- Independent context does not inherit every parent fact automatically; the main agent must provide a minimum complete, unambiguous task packet.
- Every subagent consumes model and tool resources. Multiple agents do not inherently save tokens.
- Independent context is not permission isolation. System read-only status requires a read-only parent session or runtime evidence.

## Minimum Delegation Packet

1. Functional boundary, goals, and non-goals.
2. Current phase, execution profile, risk, and stopping conditions.
3. Baseline, HEAD, packet hash, and freshness.
4. Unique responsibility, file/symbol/call-chain scope, and exclusions.
5. Existing validation, failures, unverified items, and evidence index.
6. Permitted/prohibited operations and isolation level.
7. Approved dispatch profile, permit reference, reserved units, and result schema.

## Return to the Main Session

- Checked scope.
- Consolidated root-cause findings.
- Evidence levels, unverified items, and necessary validation.
- Approved dispatch profile, reserved units, and isolation state.
- Brief conclusion.

Do not return the full parent session, complete diff, long raw logs, every file, or internal reasoning.

## Dispatch Profiles

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

- Luna: read-intensive, bounded, repetitive, structured subtasks.
- Terra Medium: business semantics, multi-file logic, and ordinary specialist judgment.
- Terra High: transactions, concurrency, security, irreversible migration, core state machines, and blocking conflicts.
- Automatic flows never exceed Terra High and never use Sol, `xhigh`, `max`, or `ultra`.
- Exact model requests are validated only transiently before dispatch; Agents do not read, infer, or report host runtime model identity.

## Harness Principle

V7.4 follows “a map, not a thousand-page manual”: global rules define boundaries and routing; Skills provide on-demand capability; scripts maintain state, evidence, idempotency, and gates; repositories and external memory retain verifiable facts.
