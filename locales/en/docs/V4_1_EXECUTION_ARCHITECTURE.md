# V4.1 Deterministic Execution Architecture

> Historical design document: V4.2 replaced its default budgets and flow. Current rules are defined by `V4_2_COST_FLOW_OPTIMIZATION.md`, `MODEL_ROUTING_AND_COST_POLICY.md`, and actual scripts.

## Goal

Without adding more Skills, move existing capabilities from “complete rules” to restrained scheduling, recoverable state, invalidatable evidence, isolated subagent context, diagnosable installation, and verifiable results.

## Core Components

```text
Global rules: authorization, profiles, phases, and Skill routing
        ->
Domain Skills: technical knowledge loaded on demand
        ->
Execution Envelope: goals, permissions, phases, gates, and stopping conditions
        ->
execution_guard: repository fingerprints and evidence validity
        ->
Independent-context subagents: specialist exploration and Reviewers
        ->
review_packet + review_controller: common baseline, budget, and results
        ->
Long-term memory: recovery across compaction and sessions
```

## V4.1 Improvements

1. Split large references for progressive problem-domain loading.
2. Add `LIGHT / STANDARD / STRICT` execution profiles.
3. Add the `IDENTIFY -> PLAN -> IMPLEMENT -> VALIDATE -> REVIEW -> DELIVER` state machine.
4. Bind validation and review evidence to Git/diff fingerprints and invalidate on change.
5. Standardize review packets, structured schemas, and cost tiers.
6. Give subagents independent contexts with minimum task packets and summarized returns.
7. Support installer dry-run, doctor, backup, and rollback.
8. Validate versions, old names, Skill references, paths, and isolation semantics.
