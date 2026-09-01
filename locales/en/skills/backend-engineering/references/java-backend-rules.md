# Java, Spring, and JVM Backend Stack Index

> This index adds Java, Spring, and JVM specifics. `backend-core-rules.md` owns shared interface, business, security, job, and resource rules. Load only the sections needed now.

## Loading Index

| Reference | Content | Load When |
|---|---|---|
| `java-core-version.md` | Java project role, versions, and general coding rules | Project identification, version compatibility, Java 8/17/21, or general Java work |
| `java-architecture-framework.md` | Java layering, Spring, transactions, and persistence | Controller/Service/Repository, Spring, transactions, MyBatis, or JPA |
| `java-concurrency-integration.md` | Connection pools, concurrency, tasks, integrations, and streaming | Thread pools, async work, scheduling, Redis/MQ/HTTP, APIs/time/serialization, files, or SSE |
| `java-security-performance-testing.md` | Security, dependencies, microservices, JVM, performance, testing, and mixed architectures | Security, dependencies, JVM/performance, code review, service decomposition, or Java/Python systems |

## Loading Principles

- Identify the primary problem domain for the current phase, then load the minimum necessary references.
- Cross-domain work may combine references, but each reference must have one explicit responsibility.
- After the phase ends, unrelated references are no longer active context.
- Concrete code, configuration, logs, and runtime evidence always take precedence over general reference guidance.
