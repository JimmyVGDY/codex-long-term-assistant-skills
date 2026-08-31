# Logs, Metrics, Traces, Profiles, Alerts, and Change Events

## 4. Observability Evidence-Source Model

### 4.1 Logs

Use logs to confirm discrete events, exception chains, business states, retries, and recovery. Account for sampling, rotation, asynchronous writing, incorrect log levels, and log injection.

### 4.2 Metrics

At minimum, distinguish:

- traffic: request volume, task volume, and message production or consumption rate;
- errors: error rate, failure types, timeouts, retries, and fallbacks;
- latency: mean, P50, P95, P99, and long-tail latency;
- saturation: CPU, memory, GC, threads, connection pools, queues, disks, networks, and GPU;
- business metrics: success rate, state distribution, backlog, and completion time.

Record aggregation interval, label filters, missing values, sampling, and cardinality. Do not substitute means for tail latency, and do not turn aggregate correlation into per-request causality.

### 4.3 Distributed Traces

Check:

- root spans, critical paths, and slowest spans;
- upstream and downstream parent-child relationships, asynchronous boundaries, and cross-thread context;
- duplicate spans introduced by retries;
- sampling policy, missing spans, and clock offsets;
- duration of HTTP, database, Redis, message-queue, file, and model calls;
- error status, timeouts, and cancellation propagation.

A trace represents sampled requests only. Absence of an abnormal trace does not prove all requests are healthy.

### 4.4 Profiling and Dumps

Existing JFR, heap dumps, thread dumps, GC logs, py-spy, cProfile, flame graphs, or GPU profiles may be analyzed read-only. New online collection is separately authorized; in production, bound duration, frequency, output size, and stopping conditions.

Focus on:

- CPU hotspots, lock contention, and blocked threads;
- heap, off-heap, retained objects, and memory growth;
- GC pauses, allocation rate, and large objects;
- Python event-loop blocking, the GIL, and multiprocessing;
- GPU VRAM, kernels, data transfer, and waits;
- consistency between profiles and logs, metrics, or traces in the same time window.

### 4.5 Alerts and Change Events

Correlate:

- alert firing, recovery, and suppression;
- release, rollback, configuration refresh, scaling, and traffic switching;
- database DDL, indexes, dependency versions, and infrastructure changes;
- scheduled tasks, batch jobs, business events, and external dependency failures.

An alert is not a root cause, and a failure after a release does not automatically prove that the release caused it.

### 4.6 Correlating Multiple Evidence Sources

Build a common-time-zone chain:

```text
Change event -> Metric anomaly -> Critical trace path -> Logs/stack -> Profile resource evidence -> Recovery event
```

For each conclusion, record supporting evidence, counterevidence, gaps, and evidence level. When one evidence source is insufficient, retain the item explicitly as unverified.

---
