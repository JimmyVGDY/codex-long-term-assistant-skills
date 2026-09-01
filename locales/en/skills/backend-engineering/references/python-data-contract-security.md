# Databases, Migrations, Contracts, Money, Time, Serialization, and Security

## 7. Databases, ORMs, and Migrations

### 7.1 Sessions and Transactions

For SQLAlchemy, the Django ORM, or similar systems, check session lifecycles, transactions, autocommit, autoflush, lazy loading, N+1 access, batching, connection pools, connection leaks, long transactions, and lock waits.

Manage a database session independently for each request or task: commit on success, roll back on error, and always close it. Never share a session across threads, processes, or long-running tasks.

Do not create a session before enqueueing an asynchronous task and then pass it to the worker. Put only primary keys, business identifiers, immutable parameters, and object-storage references in the message; the worker must reload its own data.

### 7.2 Migrations

Use formal tools such as Alembic or Django migrations:

- never edit an already-applied historical migration;
- introduce changes through incremental migrations;
- evaluate table locks, table rebuilds, and coexistence of old and new application versions;
- separate large-data backfills from DDL;
- make backfills support batching, rate limits, retries, checkpoints, and compensation;
- prepare a rollback or recovery plan before production execution.

Changing an ORM model does not mean the database has been updated safely.

---

## 8. APIs, Decimal, Time, and Serialization

### 8.1 API Contracts

Check types, required fields, defaults, lengths, enums, time zones, pagination, responses, error codes, field compatibility, and idempotency.

Schema validation does not replace authorization, business rules, state validation, or data-consistency validation.

### 8.2 Money

Use `Decimal` for money; never use `float`. Define precision, rounding, database types, and JSON serialization.

### 8.3 Time

Define database, API, system, and UI time zones. Avoid mixing naive and aware datetimes. Scheduled jobs must specify the business time zone.

### 8.4 Serialization

Check Decimal, datetime, UUID, Enum, ORM objects, large integers, and binary data. Do not rely on implicit serialization that makes API formats unstable.

---

## 9. Authentication, Authorization, and Security

Proactively check:

- password hashing, token expiry, refresh, revocation, and sessions;
- CSRF, CORS, cookie security attributes, and JWT algorithms;
- API permissions, data authorization, tenant isolation, and privilege escalation;
- SQL injection, command injection, SSRF, path traversal, template injection, and deserialization;
- exposure of OpenAPI and administrative endpoints.

For uploads, check size, MIME type, extension, file signature, randomized file name, storage path, malicious content, and execute permissions.

Never use plaintext passwords, weak hashes, or uncontrolled deserialization.

---
