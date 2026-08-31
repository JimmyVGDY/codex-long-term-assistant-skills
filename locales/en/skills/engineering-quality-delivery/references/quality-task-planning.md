# Task Classification, Prechange Planning, and Preimplementation Gates

## 1. Task Types and Response Modes

### 1.1 Code Review, Analysis, and Optimization

Provide as applicable:

- functional explanation;
- current problem and goal;
- bugs and null, concurrency, SQL, transaction, performance, security, compatibility, and maintainability issues;
- recommended design, modification boundary, and benefit;
- complete code, patch, or explicit modification points;
- actual validation results and additional findings.

Omit categories that do not exist; do not fill a template mechanically.

### 1.2 Troubleshooting

Provide as applicable:

1. Symptom.
2. Known evidence and evidence level.
3. Analysis of logs, configuration, monitoring, and recent changes.
4. Candidate causes ordered by probability, risk, and validation cost.
5. Validation steps stating action, observation, and meaning of each outcome.
6. Temporary mitigation, permanent repair, longer-term improvement, and prevention.

Do not declare a unique root cause when evidence is insufficient.

### 1.3 System and Architecture Design

As needed, include requirements, flows, modules, boundaries, Mermaid architecture, database and indexes, APIs, caches, messages, search, authorization, deployment, concurrency, availability, cost, risk, phased roadmap, and acceptance.

Do not add microservices, message queues, Redis, Elasticsearch, or Kubernetes mechanically to a simple system.

### 1.4 Technical Documentation and Reports

Default to Markdown with formal, professional, neutral, directly deliverable language. Do not exaggerate unverified conclusions or force every section into a simple document.

---

## 2. Prechange Workflow

Before making a real change, complete applicable steps:

1. Confirm project, repository, branch, and baseline commit.
2. Confirm execution profile and independent authorization boundaries.
3. Read complete target-code context and critical call chains.
4. Define goals, non-goals, modification scope, and prohibited scope.
5. Identify API, database, cache, message, file, and configuration contracts.
6. Define minimum targeted validation, review, and acceptance.
7. For high risk, prepare feature flags, staged rollout, stopping, and rollback.

When facts are sufficient and the action is authorized, proceed without repeatedly asking about low-risk reversible details.

### 2.1 High-Risk Preimplementation Design and Impact Gate

Before coding, create a reviewable design and combine `$multi-agent-independent-review` for one lightweight preimplementation review when work affects:

- public API, message, cache, file, or serialization contracts;
- database DDL, migrations, historical backfills, and coexistence of versions;
- authentication, API authorization, data authorization, and tenant isolation;
- core state machines, money, inventory, task states, and idempotent success boundaries;
- cross-service decomposition, data ownership, asynchronous paths, and fault isolation;
- high concurrency, resource budgets, or GPU/NAS/object-storage migration;
- production migration, difficult staged rollout, or irreversible operations.

Use at most one round and one or two logically read-only reviewers by default, recording runtime isolation. They count toward the default six-reviewer budget for the functional boundary. Do not apply mechanically to a local low-risk repair. This gate reviews design boundaries and expensive risks; it does not replace minimum validation or independent review after implementation.

---
