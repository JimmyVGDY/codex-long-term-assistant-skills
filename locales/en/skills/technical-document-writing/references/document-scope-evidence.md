# Document Goals, Prerequisites, and Evidence Management

## Contents

- 1. Goals
- 2. Prerequisites for Writing
- 3. Facts and Evidence Management

## 1. Goals

Technical documentation should not accumulate sections for their own sake. It should enable the intended reader to:

1. understand current state, problems, goals, and constraints accurately;
2. judge whether a design is correct, implementable, verifiable, and reversible;
3. identify implementation scope, ownership boundaries, dependencies, and risks;
4. reuse it during later development, testing, deployment, operations, and audit;
5. distinguish confirmed facts, inferences, plans, and unverified items.

Documentation must support real decisions and execution. Do not add content merely for length, formality, or the appearance of professionalism.

---

## 2. Prerequisites for Writing

Before creating or modifying a document, identify the following.

### 2.1 Document Type

Determine whether the task is primarily:

- a technical solution or implementation proposal;
- a system or architecture design;
- an API or data-contract design;
- a database, cache, message-queue, or search design;
- a deployment, operations, staged-rollout, or rollback runbook;
- an incident analysis, repair report, or postmortem;
- a code review, performance assessment, or security assessment;
- a technology selection, feasibility assessment, or option comparison;
- a project progress, delivery, or management report;
- a README, development guide, or knowledge note;
- an organization, summary, rewrite, or format conversion based on existing materials.

### 2.2 Intended Readers

Readers need different levels of detail:

- Developers: code boundaries, APIs, data structures, exceptions, and validation.
- Test engineers: acceptance criteria, test scope, data preparation, and regression risk.
- Operations: deployment steps, configuration, monitoring, stopping conditions, and rollback.
- Architects or technical leads: boundaries, tradeoffs, capacity, extensibility, and cost.
- Product or business stakeholders: business goals, processes, impact, and acceptance criteria.
- Management: context, conclusions, risks, resources, plans, and required decisions.
- Audit or security teams: evidence, permissions, records, data, and compliance boundaries.

Do not serve every audience with the same density of technical detail.

### 2.3 Document Purpose

Define whether the document supports:

- discussion and decision-making;
- implementation;
- review and acceptance;
- release approval;
- production operations;
- incident review;
- handoff;
- training and knowledge retention;
- external or cross-department communication.

Purpose determines the need for versioning, approval, procedures, rollback, evidence, and attachments.

### 2.4 Delivery Boundary

Confirm:

- output format: Markdown, DOCX, PDF, web page, or plain text;
- new document or modification of an existing one;
- permission to write into the repository;
- need to update indexes, README, or CHANGELOG;
- need for diagrams, Mermaid, tables, or attachments;
- required organizational, project, or existing templates;
- need for a local commit, push, or publication.

Without the corresponding authorization, provide content or recommendations only; do not write, overwrite, commit, or publish autonomously.

---

## 3. Facts and Evidence Management

### 3.1 Source Priority

Technical facts normally rank in this order:

1. actual runtime results, tests, monitoring, and reproducible evidence;
2. current code, configuration, database schema, and artifacts;
3. current logs, database state, middleware state, and command results;
4. current Git state, commits, and diffs;
5. formal current contracts, migration records, and project documentation;
6. project facts explicitly confirmed by the requester;
7. historical material and general engineering experience.

When sources conflict, list the conflict explicitly; do not silently select the more convenient conclusion.

### 3.2 Writing from Supplied Materials

When organizing attachments, code, logs, or existing documents:

- treat those materials as the primary source;
- preserve their terminology, business definitions, organization, and level of detail;
- do not replace them with familiar but different business concepts;
- do not silently correct facts, numbers, or conclusions;
- label obvious conflicts or errors as “Needs confirmation” or “Suggested correction”;
- state “Not covered by the available material” when information is absent;
- when expansion, verification, or external research is requested, separate source-derived conclusions from external additions.

### 3.3 Evidence Levels

Label important conclusions as needed:

- **Confirmed**: direct code, configuration, log, test, monitoring, or execution evidence exists.
- **Highly likely**: strong evidence exists, but full reproduction or closure is missing.
- **Inference**: derived from engineering reasoning and current clues.
- **Assumption**: a temporary premise used to advance the design.
- **Unverified**: currently impossible to verify.
- **Needs confirmation**: must be confirmed by a business or environment owner.

Plans, goals, and recommendations must not be written as completed facts.

### 3.4 No Fabricated Evidence

Never fabricate:

- passing tests, successful builds, load-test results, or performance gains;
- code paths, endpoints, fields, configuration, schemas, or versions;
- commits, release times, deployment state, or production recovery;
- account counts, concurrency, schedule, budget, or resource commitments;
- incident causes, responsible parties, or business impact;
- meeting conclusions, approval status, or personal commitments.

Without evidence, use bounded conditional language rather than absolutes such as “ensures,” “completely resolves,” or “has no impact.”

---
