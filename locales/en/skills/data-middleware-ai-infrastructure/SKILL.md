---
name: data-middleware-ai-infrastructure
description: Use for SQL databases, Redis, messaging, search, vector retrieval, storage, GPU resources, containers, orchestration, networks, and infrastructure.
---

# Data, Middleware, AI, and Infrastructure

1. Establish component versions, topology, ownership, contracts, capacity, environment, and operational boundaries.
2. For databases, inspect plans, indexes, transaction locks, DDL compatibility, rollout, and rollback.
3. For Redis, inspect penetration, stampede, avalanche, hot keys, large keys, TTL, and lock ownership.
4. For messaging, inspect confirmation, acknowledgement, idempotency, retry, dead letters, order, and backlog.
5. For AI, RAG, and GPU work, inspect output validation, authorization filtering, injection, timeout, degradation, queues, memory, cancellation, and recovery.
6. For containers and orchestration, inspect image provenance, resource limits, probes, graceful shutdown, configuration, secrets, rolling release, and rollback.

A database transaction cannot cover Redis, messaging, HTTP, object storage, or model calls. Large data volume alone does not justify higher reasoning effort. Production and infrastructure writes need separate authorization.
