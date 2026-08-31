# Document-Type Selection and Writing Playbooks

## Contents

- 1. Selection Matrix
- 2. Technical Solution Playbook
- 3. Architecture Design Playbook
- 4. Implementation Plan Playbook
- 5. API and Database Design Playbook
- 6. Incident Report Playbook
- 7. Code Review Playbook
- 8. Management Report Playbook

Use this file to choose a structure after identifying the document type. Read only the sections relevant to the current task.

## 1. Selection Matrix

| Objective | Recommended Template | Common Supporting Skills |
|---|---|---|
| Propose a technical change or repair | `TECHNICAL_SOLUTION.template.md` | Relevant domain skill, quality delivery |
| Design a complete system or architecture | `ARCHITECTURE_DESIGN.template.md` | Java, Python, frontend, or data infrastructure |
| Create a phased implementation plan | `IMPLEMENTATION_PLAN.template.md` | Quality delivery, long-running task memory |
| Design an API contract | `API_DESIGN.template.md` | Java, Python, frontend, security and data rules |
| Design database tables and indexes | `DATABASE_DESIGN.template.md` | Data infrastructure, quality delivery |
| Write a deployment or production runbook | `DEPLOYMENT_RUNBOOK.template.md` | Data infrastructure, quality delivery |
| Analyze a production incident | `INCIDENT_REPORT.template.md` | Relevant domain skill, quality delivery |
| Report code-review results | `CODE_REVIEW_REPORT.template.md` | Relevant domain skill, quality delivery |
| Report project progress and delivery | `PROJECT_PROGRESS_REPORT.template.md` | Long-running task memory, quality delivery |
| Compare technology choices | `TECHNICAL_SELECTION.template.md` | Relevant domain skill |
| Document a project | `README.template.md` | Relevant domain skill |
| Submit a formal management or cross-department report | `MANAGEMENT_REPORT.template.md` | Relevant domain skill |

## 2. Technical Solution Playbook

Use for “how should this be changed,” “how should this be optimized,” “how should it be migrated,” or “how should it be solved.”

Recommended process:

1. Read current state and evidence.
2. Define goals, non-goals, and constraints.
3. Analyze the root cause or core conflict.
4. Present at least two candidate options, or explain why only one is reasonable.
5. Compare cost, risk, performance, compatibility, and rollback.
6. State the recommendation and its applicable conditions.
7. Implement in phases.
8. Define validation, monitoring, stopping conditions, and rollback.
9. Preserve unverified items.

## 3. Architecture Design Playbook

Use for system design, a new platform, service decomposition, or major refactoring.

Recommended order:

1. Requirements and scale.
2. Business flow.
3. System boundaries.
4. Module and service responsibilities.
5. Architecture diagrams and critical sequences.
6. Data ownership and consistency.
7. APIs, caching, message queues, search, and files.
8. Authorization, security, and audit.
9. Concurrency, availability, and fault isolation.
10. Deployment, monitoring, cost, and evolution.
11. Risks, acceptance, and rollback.

## 4. Implementation Plan Playbook

Use when the design is chosen and phases, dependencies, and validation must be scheduled.

Every phase must answer:

- Why now?
- What changes?
- What does not change?
- What are the dependencies?
- How is it validated?
- Where does work stop on failure?
- How is it rolled back?
- What evidence proves completion?

Use “Needs confirmation” for schedule or owner fields without evidence; do not invent commitments.

## 5. API and Database Design Playbook

Design APIs from caller needs and business contracts; design databases from data ownership, query patterns, and consistency. Both must check:

- authorization and tenants;
- idempotency and duplicate requests;
- field compatibility;
- time, money, and enums;
- pagination and batch limits;
- historical data and coexistence of old and new versions;
- error and exception paths;
- audit and observability.

## 6. Incident Report Playbook

While an incident continues, call the document an “Incident Analysis and Response Record.” Use “Incident Postmortem” only after validating root cause and recovery.

Strictly distinguish:

- externally observed symptoms;
- system evidence;
- candidate causes;
- confirmed root cause;
- temporary measures;
- permanent repair;
- recovery validation;
- recurrence prevention.

## 7. Code Review Playbook

Review conclusions must refer to actual files, diffs, or call chains. Each issue should include:

- location;
- evidence;
- risk;
- severity;
- recommendation;
- whether it blocks delivery.

Omit categories with no findings; do not use an empty template to create the appearance of a completed review.

## 8. Management Report Playbook

For management readers, put conclusions before supporting detail:

1. Executive summary.
2. Current state.
3. Core problems.
4. Recommended solution.
5. Resources and plan.
6. Risks and controls.
7. Required decisions.

Place technical details in an appendix or “Technical Basis” section so source code and configuration do not overwhelm the main report.
