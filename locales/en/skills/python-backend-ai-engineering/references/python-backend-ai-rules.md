# Python Backend and AI Engineering Rules

> V5.0 retains the on-demand references introduced in V4.1. Read this index first and load only the sections needed for the current task; never load every file merely for formality.

## Loading Index

| Reference | Content | Load When |
|---|---|---|
| `python-core-web-frameworks.md` | Python project identification, layering, and Web frameworks | Python versions, FastAPI/Django/Flask, and API layering |
| `python-concurrency-deployment.md` | Sync/async execution, GIL, multiprocessing, and deployment | Event loops, threads/processes, CPU/GPU work, and Web deployment |
| `python-data-contract-security.md` | Databases, migrations, contracts, monetary values, time, serialization, and security | ORM/Session, migrations, API contracts, Decimal, authentication, and authorization |
| `python-tasks-quality-testing.md` | Celery, multiple Workers, code quality, dependencies, and testing | Task queues, in-process state, typing, exceptions, dependencies, tests, and code review |

## Loading Principles

- Identify the primary problem domain for the current phase, then load the minimum necessary references.
- Cross-domain work may combine references, but each reference must have one explicit responsibility.
- After the phase ends, unrelated references are no longer active context.
- Concrete code, configuration, logs, and runtime evidence always take precedence over general reference guidance.
