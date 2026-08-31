# Safe Production Operations

## 9. Production Constraints

### 9.1 Read-Only by Default

Production permits only viewing logs, configuration, processes, containers, pods, ports, resources, monitoring, Git state, middleware state, and read-only database queries by default.

Changing code, configuration, data, caches, messages, files, Nginx, networking, tasks, traffic, releases, rollback, restart, or scaling requires explicit current-task authorization.

### 9.2 Preflight Confirmation

Before a production write, confirm:

- environment, host, cluster, service, and instance;
- current version, branch, image, and artifact;
- database and middleware targets;
- traffic and impact scope;
- backup, rollback, acceptance, and stopping conditions.

Do not write when the environment cannot be confirmed.

### 9.3 High-Risk Operations

Operations such as `rm -rf`, DROP, TRUNCATE, unconditional DELETE, broad UPDATE, FLUSH, purge, deleting indexes, objects, or volumes, `git reset --hard`, `git clean`, force-push, restarting every instance, or disabling authentication or audit require a separate description of impact, backup, and rollback plus explicit authorization.

### 9.4 Production Databases

Before modifying:

1. Run a SELECT with the same conditions.
2. Confirm affected row count.
3. Back up affected data.
4. Use a primary key or explicit indexed condition.
5. Prepare recovery SQL.
6. Batch when needed.
7. Validate and record actual impact after each batch.

### 9.5 Release and Restart

Prefer one instance, small traffic, selected accounts, staged observation, gradual rolling expansion, then full release. Do not restart every instance by default.

Before restart, check long tasks, transactions, unacknowledged messages, SSE, file transfers, graceful shutdown, and traffic draining.

### 9.6 Stopping Conditions

Stop expansion when error rate, latency, resources, connections, slow SQL, lock waits, message backlog, success rate, experience, data consistency, or actual impact exceeds expectations. Preserve state, collect evidence, and roll back according to the prepared plan.

### 9.7 Postoperation Validation

Validate service health, logs, core APIs and pages, persisted data, messages, Redis, files, SSE, latency, error rate, resources, and data consistency.

Record operation time, environment, target, command, file, configuration, commit or image, script, impact, validation, rollback, and residual risk.

---
