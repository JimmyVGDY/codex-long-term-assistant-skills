# Security, Dependencies, Microservices, JVM, Performance, Testing, and Hybrid Architecture

## 14. Security, Dependencies, and Microservices

### 14.1 Java Security

Check authentication, API authorization, data authorization, tenant isolation, horizontal and vertical privilege escalation, CSRF, CORS, XSS, SQL injection, command injection, SSRF, path traversal, uploads, deserialization, SpEL, OGNL, template injection, XXE, open redirects, and log injection.

Authorization must be enforced on the server. For legacy Struts2, pay additional attention to OGNL, dynamic method invocation, uploads, interceptors, and vulnerabilities in older versions.

### 14.2 Maven and Gradle

Check direct and transitive dependencies, version conflicts, scopes, BOMs, plugins, JDK compatibility, CVEs, licenses, repository sources, and build reproducibility.

Without explicit authorization, do not perform major-version upgrades, upgrade unrelated dependencies, replace the core framework, or modify global Maven settings.

When resolving a conflict, inspect the dependency tree and actual runtime version first, then apply the smallest exclusion and verify compatibility.

### 14.3 Spring Cloud

For microservices, check service registration and discovery, configuration services, gateways, load balancing, rate limiting, circuit breaking, fallbacks, timeouts, retries, tracing, staged rollout, health checks, and graceful deregistration.

Prevent retry amplification across layers, inconsistent timeouts, inconsistent state after dynamic refresh, and long synchronous call chains. A Spring Boot project does not automatically require Spring Cloud.

---

## 15. JVM, Performance, Logging, and Testing

### 15.1 JVM

Analyze heap, metaspace, direct memory, thread stacks, garbage collection, large objects, class loading, ThreadLocal, local caches, and container limits.

Do not solve every problem by increasing heap size. Combine GC logs, heap dumps, thread dumps, NMT, JFR, jcmd, jstack, and monitoring to distinguish heap leaks, off-heap leaks, excess threads, classloader leaks, and container constraints.

### 15.2 Performance

For performance problems, separately examine SQL, connection pools, Redis, message queues, locks, thread pools, GC, serialization, networking, file I/O, logging, regular expressions, large objects, collections, algorithms, and third-party SDKs.

Where possible, establish baselines for QPS, mean latency, P95 and P99, error rate, CPU, memory, GC, threads, queues, connections, SQL, and message backlog. Without measurements, do not claim a dramatic optimization or zero performance impact.

### 15.3 Logging

Standardize trace ID, request ID, task ID, message ID, operation ID, redacted account identifier, service, instance, state, latency, retries, and failure reason.

Do not swallow exceptions, print the same stack trace repeatedly, emit large INFO volumes inside tight loops, or log passwords, tokens, cookies, large request or response bodies, file contents, or complete model output. Do not leave verbose DEBUG or full SQL logging enabled indefinitely in production.

### 15.4 Testing

Select JUnit, Mockito, Spring Boot Test, MockMvc, WebTestClient, Testcontainers, WireMock, Awaitility, or similar tools according to the change scope.

Focus on test isolation, data cleanup, transaction rollback, mock boundaries, external services, time, concurrency, repeated runs, and execution order. In legacy Java 8 projects, follow the existing test system instead of forcing a framework upgrade for a small test addition.

Fully mocked unit tests do not replace real integration validation.

---

## 16. Additional Java Review Checklist

In addition to the general six-axis review, check:

- `equals`, `hashCode`, and `compareTo`;
- exposure of mutable collections, global mutable static state, and singleton thread safety;
- ThreadLocal leaks, lock granularity, and thread-pool configuration;
- Future exceptions, ineffective transactions, and connection leaks;
- closing file streams, HTTP responses, and Stream resources;
- reflection, type erasure, casts, BigDecimal, and time handling;
- serialization, enums, cyclic dependencies, and bean-initialization side effects;
- logging and regex performance, collection capacity, batching, idempotency, and retry storms;
- temporary files, sensitive information, and dependency vulnerabilities.

When reporting a problem, distinguish among language, framework, database, concurrency, JVM, deployment, architecture, and legacy compatibility. Do not reduce the cause to “Java is slow” or “Spring is broken.”

---

## 17. Service Decomposition and Java/Python Hybrid Architecture

When performance or maintainability problems appear, do not jump directly to microservices. First determine whether modularization, SQL repair, transaction boundaries, thread pools, worker isolation, caching, asynchrony, or deployment scaling can solve the problem.

Decomposition should follow business, data, and transaction boundaries; release independence; fault isolation; scaling needs; and team and operational cost—not technology preference.

A Java/Python hybrid architecture must define:

- the unified entry point, authentication and authorization, and owner of master business data;
- ownership of transactions and business state;
- boundaries for AI, media, and compute tasks;
- task IDs, trace IDs, idempotency keys, and error codes;
- timeout, retry, cancellation, and version rules for HTTP, gRPC, and message queues;
- staged rollout and data compatibility between old and new versions.

Avoid uncontrolled writes to the same data from both sides, divergent state models, duplicate execution after timeouts, and cyclic dependencies formed by mutual synchronous calls.
