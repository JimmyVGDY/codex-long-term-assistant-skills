# Unified Timeline, Clustering, Correlation, and Root-Cause Validation

## Contents

- 5. Standard Analysis Process

## 5. Standard Analysis Process

### 5.1 Inventory Inputs

Build a log inventory:

| Source | Environment | Service/Instance | Time Range | Time Zone | Format | Size | Completeness | Sensitivity |
|---|---|---|---|---|---|---:|---|---|

Identify:

- rotation, missing data, sampling, truncation, and out-of-order records;
- multiline stacks and interleaved asynchronous logs;
- the same event recorded repeatedly by multiple layers;
- clock drift and inconsistent time zones;
- whether DEBUG, INFO, WARN, and ERROR semantics are trustworthy;
- log flooding or missing critical events.

### 5.2 Normalize Time and Correlation Fields

- Convert all timestamps to an explicit common time zone.
- Preserve both original and normalized timestamps.
- Identify precision differences such as milliseconds, seconds, and nanoseconds.
- Correlate by trace ID, request ID, task ID, message ID, account or business identifier, thread, process, pod, and instance.
- Without a correlation ID, construct a weak correlation from time, endpoint, object ID, error code, and upstream or downstream events, and label its evidence strength.

### 5.3 Screen and Cluster

At minimum, check:

- first and last anomaly;
- error peaks, duration, and recovery point;
- exception types, error codes, stack fingerprints, and message templates;
- timeouts, retries, circuit breaking, fallbacks, cancellation, and compensation;
- connection pools, thread pools, queues, locks, GC, OOM, disks, and networks;
- business-state changes, partial success, and duplicate processing;
- different symptoms caused by one root cause;
- configuration, release, traffic, and dependency changes before and after the anomaly.

Do not count only `ERROR`. Root causes often appear in warnings, latency, connection waits, retries, or state logs.

### 5.4 Build a Timeline

At minimum, include:

- time;
- service or instance;
- event;
- correlation ID;
- evidence location;
- evidence level;
- significance to the failure chain.

Prioritize identifying:

1. the normal baseline;
2. the triggering event;
3. the first abnormal signal;
4. fault propagation;
5. retries, fallback, or recovery;
6. business impact;
7. final recovery or continuing abnormal state.

### 5.5 Correlate Across Sources

For complex tasks, analysis may be divided by source or dimension:

- application and business logs;
- databases, connection pools, and transactions;
- Redis, message queues, and Elasticsearch;
- containers, Kubernetes, system resources, and networks;
- security and access logs;
- timeline and root-cause consolidation.

Subagents must remain read-only and return structured results. The coordinating agent must:

- normalize time zones and ranges;
- deduplicate repeated events;
- resolve conflicting conclusions;
- distinguish multiple consequences of one cause from independent failures;
- produce one evidence ledger.

A simple single-file, single-service issue should not spawn agents merely for formality.

### 5.6 Root-Cause Hypotheses and Evidence Levels

Record each candidate:

| Candidate Cause | Supporting Evidence | Counterevidence/Gaps | Evidence Level | Validation Step | Validation Risk |
|---|---|---|---|---|---|

Evidence levels:

- **Confirmed**: logs and other state form a direct closed loop, or the issue is reproduced reliably.
- **Highly likely**: multiple signals agree, but one critical validation is missing.
- **Hypothesis**: technically plausible, but direct evidence is insufficient.
- **Unverified**: current logs or permissions are insufficient.

Do not:

- treat temporal sequence as causality;
- assume an observed stack trace is the initial root cause;
- ignore symptoms introduced by retries, wrapped exceptions, or downstream errors;
- generalize from one sample to all requests;
- claim an event did not happen merely because no log records it;
- merge cross-service timelines before normalizing time zones.

### 5.7 Design Validation Steps

Every step must state:

- what will be executed;
- environment and scope;
- what will be observed;
- what each possible result means;
- whether the step is read-only;
- performance and security risk;
- stopping conditions.

Prefer low-cost, low-risk, reversible validation. If production cannot be validated safely, mark the item unverified and recommend validation in staging, mirrored data, or a local reproduction.

---
