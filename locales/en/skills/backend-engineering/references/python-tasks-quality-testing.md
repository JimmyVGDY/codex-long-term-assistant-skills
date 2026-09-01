# Celery, Multiple Workers, Code Quality, Dependencies, and Testing

## 10. Celery and Asynchronous Tasks

For Celery, check the broker, result backend, serializer, acknowledgements, `acks_late`, worker loss, prefetch, retries, exponential backoff, soft and hard time limits, idempotency, cancellation, recovery, and duplicate scheduled runs.

Critical tasks must not use only the Celery task ID as business state. Maintain a business task record containing:

- business task ID, type, state, phase, and progress;
- idempotency key, retry count, and failure reason;
- creation, start, and completion times plus cancellation marker;
- trace ID, input references, and output references.

Retries must distinguish retryable failures, non-retryable failures, parameter errors, business rejections, transient downstream failures, database conflicts, and insufficient resources. Unconditional unlimited retries are prohibited.

---

## 11. Local State and Multiple Workers

In a multi-worker or multi-instance environment, process-local variables are not globally shared state.

Account sessions, distributed task state, global locks, rate-limit counters, idempotency records, business state, and shared multi-instance caches must not exist only in process memory.

Process-local caches are appropriate only for disposable, rebuildable data that does not require instance consistency and has explicit size and TTL bounds. Account for multiplied memory use and inconsistent state across workers.

---

## 12. Types, Exceptions, and Code Quality

Use type annotations, explicit return types, and data models in production code where practical. Follow the project in selecting mypy, pyright, Ruff, Black, and isort. Do not suppress findings through widespread `Any`, meaningless `cast`, or global ignores.

Do not swallow exceptions:

```python
try:
    ...
except Exception:
    pass
```

After catching an exception, handle the scenario by recording context, converting to a business exception, rolling back, cleaning up, deciding whether to retry, and re-raising when appropriate.

Proactively check:

- mutable default arguments, global mutable state, and shallow versus deep copies;
- context managers and release of files and connections;
- un-awaited coroutines, lost background-task exceptions, and event-loop blocking;
- objects shared across threads or processes;
- import-time side effects, cyclic dependencies, memory growth, and temporary files;
- uncontrolled concurrency and leaked tasks.

---

## 13. Dependencies and Testing

### 13.1 Dependencies

Identify whether the project uses requirements files, Poetry, uv, or Pipenv, and pin versions where practical. Check the supported Python range, transitive dependencies, platform and C extensions, CUDA, CVEs, licenses, and image compatibility.

Without explicit authorization, do not perform major-version upgrades, upgrade unrelated dependencies, or run an unreviewed `pip install -U` directly in production.

### 13.2 Testing

Select pytest, pytest-asyncio, HTTPX, Django TestCase, Factory Boy, Testcontainers, or similar tools according to the change scope.

Focus on fixture isolation, database cleanup, time, random data, external-service mocks, whether asynchronous tasks truly run, execution order, and stability across repeated runs.

Fully mocked unit tests do not replace integration validation.

---

## 14. Additional Python Review Checklist

In addition to the general six-axis review, check:

- mutable default arguments and global state;
- coroutines, tasks, event loops, and cancellation;
- multi-worker state plus multiplied connections and memory;
- ORM sessions, transactions, and connection leaks;
- Decimal, time zones, and serialization;
- files, temporary files, and context managers;
- import side effects, cyclic dependencies, and swallowed exceptions;
- concurrency limits, timeouts, retries, and task recovery.

When reporting a problem, distinguish among language, framework, database, concurrency model, architecture, and deployment. Do not blame Python itself without evidence.
