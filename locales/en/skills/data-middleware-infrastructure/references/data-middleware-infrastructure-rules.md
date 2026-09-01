# Data, Middleware, and Infrastructure Rules

> Read this index first and load only the sections needed for the current task. `$ai-engineering` owns model, RAG, agent, and AI-evaluation semantics.

## Loading Index

| Reference | Content | Load When |
|---|---|---|
| `data-contract-database.md` | Data contracts, relational databases, transactions, and migrations | APIs/data contracts, SQL, indexes, transactions, locks, DDL, and migrations |
| `redis-messaging.md` | Redis and messaging | Caches, distributed locks, RabbitMQ/Celery, ACK, idempotency, retries, and ordering |
| `search-storage-streaming.md` | Search, vectors, file storage, and realtime transport | Elasticsearch/vector databases, NAS/object storage/CDN, SSE, or WebSocket |
| `security-observability-runtime.md` | Security, observability, resource budgets, and runtime environments | Security/supply chain, metrics/resources, GPU resources, feature flags, Docker/Kubernetes, and networking |

## Loading Principles

- Identify the primary problem domain for the current phase, then load the minimum necessary references.
- Cross-domain work may combine references, but each reference must have one explicit responsibility.
- After the phase ends, unrelated references are no longer active context.
- Concrete code, configuration, logs, and runtime evidence always take precedence over general reference guidance.
