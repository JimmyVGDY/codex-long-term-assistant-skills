# Search, Vectors, File Storage, and Real-Time Streams

## 5. Elasticsearch, Search, and Vector Databases

### 5.1 Elasticsearch

Check:

- mappings, field types, analyzers, and dynamic mapping;
- keyword and text fields, dates, numeric values, and nested objects;
- shards, replicas, refreshes, segment merges, and disk watermarks;
- query DSL, deep pagination, aggregations, sorting, and scripts;
- index templates, aliases, ILM, and rollover indexes;
- bulk writes, version conflicts, and retries;
- authorization, sensitive fields, and tenant isolation.

Avoid unbounded wildcards, leading wildcards, excessive `size`, deep `from + size`, and high-cardinality aggregations. For deep pagination, evaluate the applicable boundaries of `search_after` and Scroll.

For index rebuilding, prefer a new index followed by an alias switch, and preserve a rollback alias. Deleting an index is a high-risk operation.

### 5.2 Vector Databases

Check vector dimensions, distance metrics, index type, filters, multitenancy, bulk writes, deletion, rebuilding, versions, and cost.

Changing the embedding model usually makes existing vectors directly incompatible, so use versioned indexes and a defined rebuild plan.

---

## 6. Files, NAS, Object Storage, and CDN

Proactively consider:

- file consistency, metadata state, and data ownership;
- object keys, upload idempotency, duplicate files, and checksums;
- multipart transfers, resumability, rate limits, timeouts, retries, and cancellation;
- full migration, incremental synchronization, staged read/write switching, and rollback;
- CDN caching, invalidation, versioned URLs, and compatibility with old assets;
- heavy NAS I/O, large directory traversal, and large-file or small-file pathologies;
- thread-pool, process, and worker isolation;
- temporary files, disk space, cleanup, and storage cost.

### 6.1 Consistency Model

Define explicitly:

- whether database metadata or the stored file object is the source of truth;
- the order of upload success, metadata commit, and message publication;
- compensation for partial success and failure;
- whether deletion is soft, delayed, or immediate;
- how synchronization tasks provide idempotency and resume from checkpoints.

### 6.2 Security

Check path traversal, unauthorized downloads, signed URLs, MIME types, file extensions, file signatures, malicious files, directory escape, and object-key injection.

Never trust an external file name as a physical path. Before deleting production objects or directories, confirm the exact scope and recovery capability.

### 6.3 NAS Resource Control

Large directory traversal, index refreshes, recursive deletion, and bulk verification are heavy-I/O operations. Protect shared storage with task queues, concurrency limits, priorities, and rate controls, but do not serialize all ordinary reads indiscriminately.

---

## 7. SSE, WebSocket, and Streaming Paths

Check across frontend and backend:

- connection establishment, heartbeats, timeouts, closure, and reconnection;
- client disconnects, server-side cancellation, and downstream task cancellation;
- message ordering, duplicates, partial messages, and last-event position;
- persistence, context saving, and recovery after refresh;
- multi-instance routing, sticky sessions, broadcasting, and gateway buffering;
- page navigation, browser suspension, and resource release;
- eventual consistency between task state and displayed state.

Do not repair only the appearance of a connection while ignoring message persistence, context, task state, leaks, or recovery.

---
