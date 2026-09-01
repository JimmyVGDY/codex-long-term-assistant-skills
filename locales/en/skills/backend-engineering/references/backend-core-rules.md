# General Backend Core Rules

## Project and runtime boundary

Identify whether the target is an API, business service, gateway, Worker, scheduler, batch process, desktop main process, or another server role. Prefer explicit task constraints, project context, build and lock files, entry points and source, containers and CI, then live runtime evidence.

Confirm the language, runtime, framework, process and concurrency model, persistence, cache, messaging, storage, external services, validation entry points, and browser/server/AI/infrastructure seams. A file extension or one dependency is not enough to classify a whole repository.

## Interface and business boundary

Protocol handlers parse requests and map responses. Application or business layers own rules, state, authorization, idempotency, and transaction orchestration. Persistence modules own queries and locking. Integration modules adapt external systems.

Check input/output isolation from persistence models, required fields, defaults, enums, time, money, pagination, errors, compatibility, retries, idempotency, partial success, and whether business behavior hides in handlers, ORM hooks, or generic utilities. Do not impose elaborate layering on a simple system, and do not compress a complex system into one global module.

## Access and security

Authentication, endpoint authorization, object access, tenant isolation, and state rules execute on the server. Check privilege escalation, injection, SSRF, path traversal, file upload, deserialization, template or command execution, redirects, sensitive logs, and dependency supply chain. Browser controls are never a substitute for server enforcement.

## Transactions and external effects

Keep application transactions around necessary database work. Check activation, commit, rollback, error propagation, timeouts, isolation, lock scope, multiple data sources, and reentry. A database transaction cannot cover Redis, messaging, HTTP, object storage, files, or model calls. Use explicit idempotency, outbox, compensation, reconciliation, or after-commit work as the risk requires.

## Concurrency, jobs, and recovery

Distinguish synchronous I/O, async I/O, CPU, GPU, and mixed work. Every thread pool, coroutine set, process pool, queue, cache, and local job collection needs capacity, timeout, cancellation, error convergence, monitoring, and shutdown. Reliable long work must survive process restart through durable task identity and state, not only in-process background execution.

## Resources, integration, and streaming

Release database connections, HTTP clients, files, temporary artifacts, locks, subscriptions, SSE/WebSocket connections, and SDK resources on success, failure, and cancellation. Reuse expensive clients, set timeouts and response limits, avoid blind retry of non-idempotent operations, and never log complete sensitive request or response bodies.

## Quality and validation

Use the project's actual unit, interface, integration, contract, concurrency, job, and end-to-end tests. Behavior changes need direct validation across relevant normal, empty, boundary, access, error, duplicate, concurrent, timeout, cancellation, and recovery paths. Performance claims require evidence across queries, connections, locks, queues, execution pools, serialization, network, files, logs, and downstream capacity.
