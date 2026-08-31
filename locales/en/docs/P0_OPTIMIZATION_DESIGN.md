# v3.2 P0 Optimization Design

> Historical design: V4.2 replaced the default budgets and flow. Current rules come from `V4_2_COST_FLOW_OPTIMIZATION.md`, `MODEL_ROUTING_AND_COST_POLICY.md`, and actual scripts.

> v3.3 correction: Reviewer `read-only` in this document means TOML configuration intent and behavioral constraints. Runtime system isolation requires separate validation under `REVIEWER_RUNTIME_ISOLATION.md`.

## 1. Goal

v3.2 does not add more domain Skills. It improves routing accuracy, preimplementation risk discovery, deterministic review budgets, observability evidence coverage, and external-memory security.

P0 scope:

1. Minimum sufficient Skill loading.
2. High-risk design and impact review before implementation.
3. Multi-agent review state controller.
4. Log Skill expansion to metrics, traces, profiling, alerts, and change events.
5. External-memory permissions, sensitive-information handling, and retention governance.
6. Skill-routing regression cases and observation tools.

## 2. Minimum Sufficient Loading

The main agent selects one primary domain Skill for the current phase and at most two supporting Skills by default. More than four active Skills requires unique responsibilities. Workflow Skills load by phase: read-only analysis does not preload Git, review, or long-term-memory rules.

This follows “each instruction once, expose only relevant tools and rules, and regress with representative tasks,” preventing large prompts and tool sets from diluting the main goal.

## 3. Preimplementation and Postimplementation Gates

### Before Implementation

Use for public contracts, database migrations, authorization, core state machines, cross-service work, high concurrency, and production migration. The historical default was one round with two to four Reviewers, focusing on expensive directional mistakes.

### After Implementation

After code and minimum validation stabilize, use one to six Reviewers across six dimensions, then attribute consistently and repair centrally.

The gates do not replace each other. The historical aggregate ceiling was twelve Reviewers per functional boundary. Current lower defaults are defined by V4.2 and later rules.

## 4. Review State Controller

`review_controller.py` does not create agents or touch project code. It maintains a JSON ledger and validates:

- pre/post phase;
- rounds, depth, parallel count, and total Reviewers;
- planning, dispatch, results, and consolidation;
- centralized repair rounds;
- controlled final conclusions.

After context compaction, read controller state before allowing another round rather than relying on conversation memory.

## 5. Multi-Signal Observability

The common evidence model includes logs, metrics, distributed traces, profiles/dumps, alerts, and deployment/configuration changes.

First normalize scope and time, then evaluate sampling, aggregation, and completeness for each source, and finally correlate sources. Correlation from one signal never becomes root cause automatically.

## 6. External-Memory Security

- Retain minimum necessary information.
- Scan common plaintext credential patterns.
- Recommend POSIX mode 700 for directories and 600 for files.
- Verify Windows ACLs manually.
- Recommend 90 days for completed tasks and 30 days for temporary analysis by default.
- Retention tools report candidates only and never delete automatically.
- Do not synchronize to cloud drives, NAS, or other devices by default.

## 7. Routing Regression

Routing tests have two layers:

1. In-package static validation of case schema, Skill names, and rule consistency.
2. Real local observation by sending each prompt in Codex, recording activated Skills, and scoring required, forbidden, and maximum active counts.

Static checks do not replace real automatic-activation observation.
