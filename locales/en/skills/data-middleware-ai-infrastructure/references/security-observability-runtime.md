# Security, Observability, Resource Budgets, and Runtime Environments

## Contents

- 10. Security, Authorization, and Supply Chain
- 11. Observability, Resource Budgets, and Feature Flags
- 12. Docker, Kubernetes, and Runtime Environments

## 10. Security, Authorization, and Supply Chain

### 10.1 Sensitive Information

Redact passwords, tokens, access keys, secret keys, cookies, sessions, identity numbers, phone numbers, bank-card data, addresses, and confidential organizational information from code, configuration, logs, and documentation.

Use explicit placeholders:

```text
<YOUR_TOKEN>
<YOUR_PASSWORD>
<YOUR_ACCESS_KEY>
<YOUR_SECRET_KEY>
```

### 10.2 Authorization

Check authentication, API permissions, data authorization, tenant isolation, horizontal and vertical privilege escalation, ID enumeration, unauthorized downloads or modifications, administrative endpoints, and audit logs.

Do not rely on hidden frontend controls. New endpoints, asynchronous entry points, callbacks, files, and task-status queries must all verify resource ownership.

### 10.3 Common Attack Surfaces

Check SQL injection, command injection, SSRF, path traversal, XSS, CSRF, unsafe deserialization, template and expression injection, XXE, open redirects, log injection, and unsafe uploads or downloads.

### 10.4 Supply Chain

When adding or upgrading dependencies, images, or scripts, check the official source, version compatibility, transitive dependencies, CVEs, license, default behavior, rollback path, and typosquatted packages.

Without explicit authorization, do not execute scripts from unknown sources, use untrusted images, or add dependencies with unknown maintenance status.

---

## 11. Observability, Resource Budgets, and Feature Flags

### 11.1 Observability

For core paths, record trace IDs, request IDs, task IDs, message IDs, redacted business identifiers, state, latency, retries, failure reasons, services, and workers.

At minimum, consider metrics for:

- request volume, error rate, P95, and P99;
- CPU, memory, GC, threads, coroutines, and processes;
- database and Redis connections;
- queue length, message backlog, and task duration;
- file I/O, disks, NAS, and object storage;
- tokens, model latency, GPU VRAM, and GPU utilization.

Logs must be locatable and correlatable, must not leak secrets or swallow exceptions, and must not emit large payloads on high-frequency paths.

### 11.2 Resource Budgets

During design and modification, evaluate:

- maximum concurrency, queue length, and per-task memory;
- thread-pool, coroutine, process, and worker counts;
- database, Redis, and HTTP connection pools;
- message-queue prefetch;
- file-size and transfer-rate limits;
- request timeouts, total retry duration, and token budgets;
- GPU VRAM and resident models.

Unbounded queues, concurrency, retries, files, or calls without timeouts are prohibited.

### 11.3 Feature Flags

For high-risk changes and core paths, prefer feature flags, configuration switches, tenant- or account-level rollout, traffic percentages, and switching between old and new paths.

Define the default, scope, disable path, monitoring metrics, rollback, and eventual cleanup. Feature flags must not accumulate permanently into unmaintainable branches.

---

## 12. Docker, Kubernetes, and Runtime Environments

### 12.1 Docker

Check:

- base-image source, version, and vulnerabilities;
- multi-stage builds, non-root accounts, and least privilege;
- image size, build caching, and reproducibility;
- environment variables, secrets, mounts, and read-only filesystems;
- health checks, graceful shutdown, logs, and time zones;
- CPU, memory, disk, and GPU limits;
- boundaries between temporary files and persistent volumes.

Never write secrets into image layers or commit them to the repository. Do not treat ad hoc changes inside a running container as a formal delivery.

### 12.2 Kubernetes

Check the choice among Deployment, StatefulSet, Job, and CronJob; Requests and Limits; probes; rolling rollout; PDB; HPA; affinity; Secret; ConfigMap; Service; and Ingress.

Prevent:

- receiving traffic before Readiness succeeds;
- restart storms caused by overly aggressive Liveness checks;
- stopping every instance during a rolling update;
- duplicate business operations caused by Job retries;
- configuration refresh and version mismatches;
- insufficient ephemeral storage, OOMKilled containers, and node-resource contention.

### 12.3 Networks and Proxies

Check DNS, timeouts, Keep-Alive, proxies, Nginx buffering, upload limits, WebSocket and SSE forwarding, TLS, and firewalls. When diagnosing a network failure, distinguish among the client, proxy, container, host, DNS, and downstream service.
