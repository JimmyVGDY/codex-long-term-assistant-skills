# Responsibilities, Input Confirmation, and Four Execution Modes

## 1. Responsibility

This workflow orchestrates observability analysis across environments and technology stacks. It covers input inventory, scope control, timelines, correlation, evidence grading, validation plans, and output structure for logs, metrics, traces, profiling, alerts, and release or configuration-change events.

It does not replace Java, Python, database, middleware, or infrastructure expertise, and it grants no automatic permission to modify code, environments, or data.

---

## 2. Confirm Before Starting

Confirm at least the following; when confirmation is impossible, state assumptions and unverified items:

- whether logs come from local files, attachments, development, testing, staging, remote environments, or production;
- file, service, container, pod, host, cluster, and instance scope;
- target problem, known symptoms, first occurrence, and impact window;
- log, system, and business time zones plus timestamp precision;
- format, encoding, line endings, rotation, and compression;
- correlation fields such as trace ID, request ID, task ID, message ID, and operation ID;
- file count, total size, available disk, and memory budget;
- real account data, secrets, privacy, or confidential organizational data;
- permitted commands, read-only queries, and temporary-file scope;
- permission for continued observation, decompression, copying, download, or parser scripts.

If only log files are provided, do not require a complete technical diagnosis in advance. Extract verifiable facts from the files first, then identify missing information.

---

## 3. Four Execution Modes

### 3.1 Static File Analysis

Applies to local `.log`, `.txt`, JSON Lines, CSV, archives, and exported container logs.

Within authorization and resource budgets, this mode may:

- read complete or chunked files;
- sort by time, level, service, and correlation ID;
- decompress into an isolated temporary directory;
- use read-only scripts to aggregate, cluster, and produce intermediate results;
- merge multi-file timelines;
- generate redacted analysis artifacts.

It must:

- never overwrite originals;
- check archives for path traversal and abnormal expansion;
- limit temporary directories, disk, memory, and file handles;
- clean temporary files only when authorized, otherwise report their location;
- label unparseable encodings, truncated lines, and damaged files.

### 3.2 Local Runtime Analysis

May inspect local applications, processes, containers, ports, resources, and logs read-only.

By default, it must not:

- restart or stop services;
- modify configuration, environment variables, or log levels;
- clean logs, caches, or data;
- modify databases, middleware, or files;
- create commits or deploy.

### 3.3 Remote Non-Production Read-Only Analysis

Development, test, and staging environments still require bounded command cost and do not imply write permission.

Prefer to:

- narrow service, instance, and time scope first;
- use `--since`, `--until`, `--tail`, or equivalents;
- count first, then read representative excerpts;
- validate with read-only monitoring and low-risk queries;
- avoid CPU, disk, or network pressure on shared environments.

### 3.4 Production Read-Only Analysis

Production permits only the currently authorized scope, such as:

- viewing logs, monitoring, processes, containers, pods, ports, and health;
- viewing read-only configuration and version information;
- executing low-risk read-only queries with explicit scope, indexes, and timeouts;
- viewing Redis, message-queue, and Elasticsearch state and statistics;
- reading the minimum necessary log excerpts.

Do not:

- modify, delete, or clean logs and files;
- change configuration or log levels, restart, deploy, scale, or switch traffic;
- write to databases, Redis, message queues, Elasticsearch, object storage, or files;
- run unbounded `tail -f`;
- run broad unbounded `grep -R`, `find`, full-disk scans, or bulk decompression;
- run Redis `KEYS *`;
- issue unindexed, broad, long-transaction, or potentially table-locking queries;
- retrieve complete large objects, message bodies, request bodies, or private data.

Read-only commands can still consume production resources. Before execution, assess time range, file volume, query plan, timeout, and stopping conditions.

---
