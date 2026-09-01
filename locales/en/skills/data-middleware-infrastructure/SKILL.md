---
name: data-middleware-infrastructure
description: Use for databases, SQL, transaction locks, Redis, messaging, search and vector storage, files, NAS, object storage, GPU resources, containers, orchestration, networks, and infrastructure. Do not use for ordinary server business logic, browser interaction, or model/RAG/agent semantics.
---

# Data, Middleware, and Infrastructure

1. Establish component versions, topology, ownership, contracts, capacity, environment, and operational boundaries.
2. For databases, inspect plans, indexes, transaction locks, DDL compatibility, rollout, and rollback.
3. For Redis, inspect penetration, stampede, avalanche, hot keys, large keys, TTL, and lock ownership.
4. For messaging, inspect confirmation, acknowledgement, idempotency, retry, dead letters, order, and backlog.
5. For vector storage and GPU resources, inspect indexes, capacity, devices, memory, drivers, queues, quotas, isolation, monitoring, and recovery. Combine `$ai-engineering` for RAG semantics, model output, agents, and AI evaluation.
6. For containers and orchestration, inspect image provenance, resource limits, probes, graceful shutdown, configuration, secrets, rolling release, and rollback.

A database transaction cannot cover Redis, messaging, HTTP, object storage, or model calls. Ordinary application APIs, business state, access, and Worker mechanics are led by `$backend-engineering`; model, RAG, agent, and generation semantics are led by `$ai-engineering`. Large data volume alone does not justify higher reasoning effort. Production and infrastructure writes need separate authorization.
