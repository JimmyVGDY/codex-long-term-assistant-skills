# Redis and Message Queues

## 3. Redis

Proactively analyze:

- cache penetration, hot-key breakdown, avalanches, and hotspot keys;
- large keys, TTLs, randomized expiration, warming, and eviction policies;
- dual-write consistency, delayed double deletion, invalidation order, and cache pollution;
- cluster slots, primary-replica failover, and consistency across instances;
- sessions, idempotency, rate limiting, and task state;
- serialization-version compatibility.

### 3.1 Keys and Values

Keys must include project, environment, business-domain, and version boundaries to prevent cross-project and cross-environment collisions. Value size, collection cardinality, and TTL must all have upper bounds.

### 3.2 Distributed Locks

Define the lock key, owner identity, timeout, renewal, unlock ownership check, failure handling, time spent inside the lock, and fallback policy.

Do not perform long remote calls, large-file processing, or unbounded waits while holding a lock. Unlocking must verify ownership to prevent deleting another owner's lock.

### 3.3 Production Operations

Never use the following directly in production:

```text
KEYS *
FLUSHALL
FLUSHDB
```

Use `SCAN` for queries. Before deleting data, confirm the item count, value size, whether the data represents sessions, locks, task state, idempotency, or rate limits, and the breakdown and recovery risks after deletion.

---

## 4. RabbitMQ, Celery, and Message Queues

Proactively check:

- publisher confirms, returned messages, durability, and routing failures;
- consumer acknowledgements, prefetch, concurrency, and connection recovery;
- message loss, duplicate consumption, idempotency, and ordering;
- retries, backoff, dead-lettering, poison messages, and terminal failure handling;
- backlogs, consumer throttling, task timeouts, and cancellation;
- network instability, multi-instance races, and message-version compatibility.

### 4.1 Success Boundaries

Acknowledgement timing must match the business success boundary. Do not acknowledge before the transaction commits, and do not repeat successful business work merely because returning the response failed.

### 4.2 Idempotency

Idempotency must not depend only on variables inside a consumer process. Depending on the scenario, use:

- database unique constraints;
- idempotency records;
- conditional state updates;
- business version numbers;
- replayable state machines.

### 4.3 Retries

State the maximum attempts, interval, exponential backoff, retryable exceptions, non-retryable exceptions, and terminal failure handling.

Never retry parameter errors, business rejections, or permanent failures indefinitely. Prevent layered retries, retry storms, and amplification of downstream load.

### 4.4 Ordering

When ordering is required, define its scope: global, per business key, per partition, or per consumer. Evaluate how concurrency, retries, and dead-letter replay can violate that order.

### 4.5 Production Operations

Without explicit authorization, do not purge queues, delete queues or exchanges, cancel all consumers, replay all dead letters, or perform mass redelivery. Before any replay, verify consumer idempotency and capacity.

---
