# Connection Pools, Concurrency, Tasks, Integration, and Streaming

## Contents

- 9. Connection Pools, Threads, and Concurrency
- 10. Scheduled Tasks and Batch Processing
- 11. Java-Specific Checks for Redis, RabbitMQ, and HTTP Clients
- 12. APIs, Money, Time, and Serialization
- 13. Files, SSE, and Resource Release

## 9. Connection Pools, Threads, and Concurrency

### 9.1 Database Connection Pools

Check maximum connections, minimum idle connections, acquisition timeout, idle timeout, maximum lifetime, leak detection, database limits, total connections across instances, long transactions, and slow SQL.

Do not enlarge a connection pool merely to mask slow queries. Recalculate the aggregate database connection count whenever application instances are added.

### 9.2 Threads and Thread Pools

Proactively check shared mutable state, visibility, atomicity, lock ordering, deadlocks, ThreadLocal, MDC, transaction propagation, and security-context propagation.

Do not:

- create arbitrary threads with `new Thread()`;
- use unbounded thread pools or queues;
- use `Executors.newCachedThreadPool()` for uncontrolled workloads;
- perform remote calls or large-file I/O while holding a lock.

Every thread pool must define core and maximum sizes, queue capacity, thread naming, rejection policy, idle timeout, task timeouts, monitoring, and graceful shutdown. Isolate ordinary requests, database work, files, NAS, external APIs, message queues, AI, video, and scheduled tasks according to their risk profiles.

### 9.3 `CompletableFuture`

Explicitly evaluate the executor, exception handling, timeouts, cancellation, result aggregation, partial failures, and context propagation. Never call `runAsync` or `supplyAsync` and then ignore the executor and exceptions.

When execution must be durable, retryable, and recoverable, prefer a message queue or task system over process-local asynchrony.

---

## 10. Scheduled Tasks and Batch Processing

For Spring Scheduler, Quartz, XXL-JOB, or similar systems, check:

- duplicate execution across instances, distributed locks, misfires, and overlapping runs;
- idempotency, sharding, compensation, retries, timeouts, and cancellation;
- time zones, cron expressions, manual triggers, execution records, and graceful shutdown.

For critical tasks, record task name, scheduled time, start and end times, state, processed count, success and failure counts, instance, and trace ID.

Batch jobs should support pagination or cursors, batched commits, rate limits, failure records, retries, checkpoint recovery, and idempotency.

---

## 11. Java-Specific Checks for Redis, RabbitMQ, and HTTP Clients

See the data and middleware module for general reliability rules. This section adds issues specific to Java clients and frameworks.

### 11.1 Redis Clients

For RedisTemplate, StringRedisTemplate, Redisson, Lettuce, or Jedis, check serialization, connection pools, timeouts, threading models, pipelines, Lua, lock renewal, and isolation of Spring configuration.

Do not change a global Redis serializer casually. Any cache-structure change must account for deserializing existing data.

### 11.2 Spring AMQP

Check publisher confirms and returns, container acknowledgements, prefetch, consumer concurrency, exception conversion, retry interceptors, dead letters, and message converters. Acknowledgement timing must match the business success boundary.

### 11.3 HTTP Clients

For RestTemplate, WebClient, OpenFeign, OkHttp, or Apache HttpClient, check connect, read, and write timeouts; connection pools; DNS; Keep-Alive; response-size limits; and resource release.

Do not create a new client per request, call without timeouts, retry non-idempotent endpoints blindly, make slow calls inside long transactions, or log complete sensitive requests and responses.

---

## 12. APIs, Money, Time, and Serialization

### 12.1 API Contracts

Check field types, required fields, lengths, defaults, enums, time formats, monetary precision, pagination limits, sort-field allowlists, error codes, version compatibility, and idempotency keys.

Bean Validation does not replace authorization, state validation, cross-field validation, or business rules.

### 12.2 Time

In modern projects, prefer `Instant`, `LocalDate`, `LocalDateTime`, `OffsetDateTime`, `ZonedDateTime`, and `Duration`. Define the time zones used by the system, database, APIs, and UI.

`LocalDateTime` has no time zone. If a legacy Java 8 system must share `SimpleDateFormat`, use thread isolation or synchronization; normally prefer creating an instance per use or using a properly cleaned `ThreadLocal`.

### 12.3 JSON

For Jackson, Fastjson, or similar libraries, check field naming, nulls, dates, time zones, enums, long-integer precision, polymorphism, unknown fields, cyclic references, sensitive fields, and deserialization safety.

Do not change the global ObjectMapper casually. Serialization changes may affect APIs, Redis, message queues, database JSON, and historical data. Older Fastjson versions require particular attention to known vulnerabilities and AutoType risks.

---

## 13. Files, SSE, and Resource Release

### 13.1 Files and Streams

Reliably release InputStream, OutputStream, Reader, Writer, JDBC, HTTP responses, ZipFile, temporary files, and file locks; prefer `try-with-resources`.

Check whether large files are streamed, file-size limits, temporary-file cleanup, encodings, path traversal, overwrite risk, and trusted file names. Never load an unbounded file into one complete byte array.

### 13.2 SSE and WebSocket

Check connection lifecycle, heartbeats, timeouts, client disconnects, server cancellation, error and completion callbacks, connection-set cleanup, thread safety, ordering, duplicate delivery, persistence, context, reconnect recovery, gateway timeouts, multi-instance routing, and session affinity.

Do not repair only “the connection never closes.” Also verify:

- whether data and context are saved;
- whether refresh restores state;
- whether task state becomes eventually consistent;
- whether caller cancellation propagates;
- whether connections or threads leak.

---
