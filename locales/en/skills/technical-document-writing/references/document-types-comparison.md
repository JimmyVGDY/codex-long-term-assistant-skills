# Document-Type Constraints and Option Comparison

## Contents

- 7. Key Constraints by Document Type
- 8. Comparing Multiple Options

## 7. Key Constraints by Document Type

### 7.1 Technical Solution

At minimum, answer:

- What are the current state and root cause?
- What are the goals and non-goals?
- What candidate options exist?
- Why does the recommendation fit the current stage?
- How does it affect APIs, data, performance, security, and compatibility?
- How will it be implemented, validated, rolled out, and rolled back?
- Under what conditions should the design be upgraded?

### 7.2 Architecture Design

Define at minimum:

- business and system boundaries;
- module or service responsibilities;
- data ownership;
- synchronous and asynchronous interactions;
- transaction and consistency boundaries;
- capacity, scaling, and fault isolation;
- authorization, security, observability, and deployment;
- cost and evolution path.

### 7.3 Implementation Plan

Each phase should include:

- objective;
- inputs and prerequisites;
- modification scope;
- outputs;
- validation;
- risks;
- stopping conditions;
- rollback point;
- dependencies.

Do not present unconfirmed dates or owners as firm commitments.

### 7.4 API Design

Define at minimum:

- purpose, callers, and authorization;
- path, method, version, and idempotency;
- request, response, error codes, and examples;
- field meaning, type, required status, length, enum, precision, and time zone;
- pagination, sorting, filtering, and batch limits;
- compatibility, rate limits, timeouts, and audit;
- sensitive fields and data authorization.

### 7.5 Database Design

Define at minimum:

- business objects and data ownership;
- tables, fields, types, defaults, and constraints;
- primary keys, unique constraints, and indexes;
- query patterns and execution-plan considerations;
- transactions, locks, concurrency, and idempotency;
- historical data, migrations, coexistence of old and new code, and rollback;
- retention, archiving, and audit.

### 7.6 Deployment and Operations Documentation

Distinguish:

- environment and target instances;
- preflight checks;
- artifacts, configuration, and secrets;
- deployment steps;
- database and middleware operations;
- health checks and business acceptance;
- monitoring metrics and observation period;
- stopping conditions and rollback steps;
- operation records.

A successful command does not prove the feature is effective.

### 7.7 Incident Report

Distinguish by evidence:

- symptoms and impact;
- timeline;
- known evidence;
- candidate causes and validation;
- confirmed root cause;
- temporary mitigation;
- permanent repair;
- recovery validation;
- recurrence prevention;
- unverified items and follow-up observation.

If the root cause is not confirmed, do not invent a single cause for completeness.

### 7.8 Code Review Report

Recommended content:

- functional understanding;
- review scope and baseline;
- bugs, null handling, concurrency, transactions, SQL, performance, security, compatibility, and maintainability findings;
- evidence, severity, impact, and recommendation for each issue;
- blocking and non-blocking items;
- unread or unverified scope;
- final conclusion.

### 7.9 Progress and Delivery Report

Distinguish:

- completed;
- in progress;
- not started;
- blocked;
- verified;
- unverified;
- committed, pushed, deployed, restarted, and effective.

Do not write only “optimization complete.” List actual deliverables, validation evidence, and residual risk.

### 7.10 Management Report

Prioritize:

- business context and goals;
- current state;
- key conclusions;
- impact scope;
- solution and resources;
- risks and controls;
- plan and required decisions.

Retain necessary technical evidence, but avoid source-code or low-level detail that does not support a decision.

---

## 8. Comparing Multiple Options

Compare at least:

| Dimension | Meaning |
|---|---|
| Business fit | Meets current requirements and business definitions |
| Implementation cost | Development, testing, migration, and training cost |
| Release risk | Change scope, downtime, data, and rollback risk |
| Performance and capacity | Latency, throughput, resources, and scalability |
| Compatibility | Legacy APIs, historical data, and coexistence of versions |
| Security | Authorization, data, and supply-chain risk |
| Maintainability | Complexity, observability, and team capability |
| Operational cost | Deployment, monitoring, incidents, and resources |
| Rollback difficulty | Ability to restore the previous path quickly |
| Applicable stage | Proof of concept, early stage, growth, or maturity |

After comparison, state:

- the recommendation;
- reasons for recommending it;
- reasons for not recommending other options;
- prerequisites;
- reevaluation or upgrade conditions.

---
