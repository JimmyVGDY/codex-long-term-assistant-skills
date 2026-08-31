# Test Selection, Minimum Validation, Adversarial, and Performance Gates

## Contents

- 3. Test Selection Principles
- 4. Minimum Targeted Validation by Change Type
- 5. Adversarial Validation
- 6. Performance and Resource Validation

## 3. Test Selection Principles

Select tests from the actual change, impact, and risk. Do not run every test mechanically, and do not skip directly related minimum validation merely because the full suite is slow or has historical failures.

### 3.1 Utility Methods

Validate normal values, nulls, boundaries, invalid input, and concurrency safety.

### 3.2 Database Logic

Validate SQL, execution plans, commit and rollback, lock conflicts, concurrent updates, unique constraints, and consistency.

### 3.3 APIs

Validate normal calls, invalid parameters, authentication, authorization, contracts, error codes, idempotency, and legacy callers.

### 3.4 Concurrency Logic

Validate repeated execution, races, lock timeouts, deadlocks, cancellation, resource release, and eventual consistency.

### 3.5 Message Queues and Tasks

Validate message loss, duplicate consumption, acknowledgements, retries, dead letters, idempotency, backlogs, timeouts, cancellation, and recovery.

### 3.6 Files

Validate empty, large, damaged, duplicate, interrupted, and timed-out files; recovery, encoding, temporary files, and path security.

### 3.7 SSE and WebSocket

Validate disconnect, heartbeat, reconnect, duplicate messages, ordering, persistence, context, page switching, and cancellation.

### 3.8 AI Output

Validate schemas, empty or invalid output, timeouts, retries, fallback, prompt injection, structured repair, and business validation.

---

## 4. Minimum Targeted Validation by Change Type

Any change to code, scripts, workers, schedulers, exports, migrations, or other executable behavior requires applicable minimum validation. Static reading alone is not enough before commit.

### 4.1 Backend Changes

Run at least one check that directly proves the changed behavior:

- relevant unit, service, controller, or API test;
- relevant database, cache, message-queue, task, or state-transition test;
- minimum reproducible validation with explicit input and output.

If the environment is incomplete, report the blocker, unverified scope, and risk. Do not call it passed.

### 4.2 Frontend Changes

Run the project's formal production build at minimum. For npm projects, normally:

```bash
npm run build
```

According to scope, validate normal, loading, empty, error, disabled, repeated click, refresh, routing, authorization, timeout, race, and frontend-backend consistency.

### 4.3 Scripts, Workers, and Scheduling

Actually run the script, execute tests, trigger the worker/scheduler, or complete a minimum reproduction.

Check input, output, abnormal exit, repeated execution, idempotency, timeouts, retries, interruption, resources, state, logs, and recovery after restart.

### 4.4 CSV, Excel, Exports, and Data Files

Actually generate or read a representative sample and check:

- header names and order;
- field mapping, data types, and nulls;
- money, quantities, ratios, totals, and subtotals;
- date/time, formatting, delimiters, quotes, and escaping;
- encoding, Chinese text, and opening in the target application;
- consistency with source data after reading.

For large data, also check streaming, memory, temporary files, duration, size, and cleanup after failure.

### 4.5 Database Migrations and Repair Scripts

Validate syntax, impact scope, forward execution, repeated execution or idempotency, failure compensation, historical compatibility, coexistence of old and new code, execution plans, and lock risk.

Production execution still needs separate production authorization.

### 4.6 Configuration Changes

Distinguish wording, build configuration, and runtime behavior configuration. Behavior changes require validation of loading, defaults, missing configuration, environment differences, restart needs, staged rollout, and rollback.

### 4.7 Failure Reports

For every failure, record:

- actual command or step;
- failing test, phase, and error summary;
- reproducibility;
- relationship to the current change and evidence level;
- whether it blocks commit;
- whether it existed before the change.

“Highly likely unrelated” is not “confirmed unrelated.”

---

## 5. Adversarial Validation

For core paths, concurrency, state, consistency, and production-risk changes, cover:

- normal, abnormal, null, and boundary inputs;
- extreme data volume;
- duplicate submissions and callbacks;
- races, timeouts, retries, interruption, and cancellation;
- partial success and failure;
- resource release and failure recovery;
- old data, legacy callers, version coexistence, and historical configuration.

Look for:

- null dereferences, bounds errors, state corruption, and duplicate processing;
- inconsistency, deadlocks, connection leaks, and thread leaks;
- coroutine, file-handle, and temporary-file leaks;
- cache pollution, retry storms, and unbounded exceptions;
- an old problem disappearing only because it moved to another path.

---

## 6. Performance and Resource Validation

When performance is affected, establish a prechange baseline where possible and compare:

- QPS, mean latency, P95, P99, and error rate;
- SQL count, latency, scanned rows, and execution plans;
- remote-call count and message latency;
- CPU, memory, GC, threads, coroutines, and processes;
- connection pools, queues, backlogs, and file I/O;
- event-loop latency, tokens, GPU VRAM, and utilization.

Do not introduce unnecessary SQL, full-table scans, remote calls, serialization, large-object copies, threads/processes, lock contention, long transactions, long connections, high-frequency logs, unbounded caches or queues, or unlimited retries.

When a full load test cannot be completed, say:

> No obvious new performance overhead was found in the changed paths and executed targeted validation; a complete performance load test has not been run.

Never claim performance is completely unaffected.

---
