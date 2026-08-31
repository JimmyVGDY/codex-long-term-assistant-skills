# Java Layers, Spring, Transactions, and Persistence

## 5. Layer and Object Boundaries

When Java is the business backend, keep responsibilities explicit:

- Controller or Endpoint: parse parameters, perform basic validation, receive authentication results, invoke services, and return standardized responses.
- Application or Service: orchestrate business work, enforce rules, manage state transitions, transactions, idempotency, and data authorization.
- Domain: hold core rules and domain objects in complex business systems.
- Repository, DAO, or Mapper: perform data access, queries, locking, batching, and pagination.
- Request, Response, DTO, VO, Entity, and PO: remain separated by purpose.
- Infrastructure, Integration, or Client: integrate middleware, files, remote services, and third parties.

Do not:

- put complex business logic, long transactions, model inference, or large-file tasks in controllers;
- scatter SQL, Redis, or message-queue operations across controllers and utility classes;
- expose database entities directly through external APIs without boundaries;
- force complex DDD into a simple project for appearance alone.

---

## 6. Spring Boot and Spring MVC

Proactively check:

- parameter validation, consistent exception handling, and response contracts;
- responsibility boundaries among filters, interceptors, and AOP;
- bean lifecycles, cyclic dependencies, and initialization side effects;
- profiles, conditional configuration, missing settings, and defaults;
- graceful shutdown, health checks, request timeouts, and upload limits;
- CORS, static resources, API documentation, and Actuator exposure;
- effects of dynamic configuration refresh on staged rollout and rollback.

Do not:

- manage complex transactions manually in controllers;
- use static Spring bean lookup as a routine design pattern;
- perform heavy network or database operations during bean construction;
- issue large volumes of database or remote calls from high-frequency AOP advice;
- convert every exception into HTTP 200;
- swallow underlying exceptions and destroy diagnostic context.

---

## 7. Spring Transactions

When `@Transactional` is involved, check:

- whether the invocation passes through a Spring proxy and whether self-invocation bypasses it;
- whether method visibility and exception type trigger rollback;
- whether caught exceptions are rethrown;
- propagation, isolation, read-only mode, timeout, and multiple data sources;
- asynchronous methods, message publication, remote calls, and file I/O;
- long transactions, lock scope, and connection occupancy.

Wrap only the required database operations in a transaction. Do not keep a transaction open during:

- HTTP, model, or third-party SDK calls;
- large-file transfers, FFmpeg work, or NAS traversal;
- long waits, extended computation loops, or blocked message consumption.

When a message must be sent after database commit, evaluate transaction synchronization callbacks, the Outbox pattern, local transactional messaging, compensation, and eventual consistency. Never assume a database transaction covers Redis, message queues, HTTP, or object storage.

---

## 8. MyBatis, MyBatis-Plus, and JPA

### 8.1 MyBatis and MyBatis-Plus

Check:

- mapper parameters, XML mappings, dynamic SQL, and empty conditions;
- empty `IN` clauses, batching, pagination, N+1 access, and field mappings;
- type handlers, enums, logical deletion, optimistic locking, and multitenancy;
- duplicate wrapper conditions, missing authorization filters, or conditions that cannot be audited;
- upper bounds and allowlists for pagination and sort fields.

Prefer `#{}` parameter binding and explicit field lists. Permit `${}` only for controlled, allowlisted table or field names; never interpolate external input directly.

### 8.2 JPA and Hibernate

Check:

- entity lifecycles, lazy loading, N+1 access, fetch strategy, and cascades;
- bidirectional relationships, orphan removal, EntityManager usage, and dirty checking;
- bulk updates, caching, pagination, optimistic locks, and pessimistic locks;
- lazy-field access outside transactions and cyclic references during JSON serialization.

Avoid indiscriminate `EAGER` loading, unbounded entity graphs, broad cascading deletes, and loading large datasets one row at a time. Critical business updates should not rely solely on implicit dirty checking.

---
