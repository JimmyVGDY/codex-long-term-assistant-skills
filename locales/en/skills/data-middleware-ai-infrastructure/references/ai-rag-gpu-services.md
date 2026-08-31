# AI, RAG, GPU, and Service Decomposition

## 8. AI, RAG, Models, and GPU

### 8.1 AI Calls

Proactively analyze:

- model capabilities and usage boundaries;
- prompts, system prompts, context windows, and token cost;
- JSON Schema, structured output, validation, and repair;
- prompt injection, sensitive information, and tool permissions;
- timeouts, retries, fallbacks, multi-model routing, and caching;
- idempotency, cancellation, failure recovery, and end-to-end tracing.

Never treat model output directly as trusted business data. Values involving money, authorization, state, or executable commands require programmatic validation.

### 8.2 RAG

Check:

- document parsing, chunk size, overlap, and metadata;
- embedding model, vector dimensions, and version;
- TopK, BM25, hybrid retrieval, RRF, reranking, and MMR;
- permission filters, multitenancy, and sensitive documents;
- data updates, deletion, rebuilding, and index consistency;
- evaluation sets, recall, accuracy, hallucinations, and citations.

RAG evaluation must not rely only on subjective examples. Establish real questions, expected evidence, and repeatable metrics.

### 8.3 Agents and Tool Calls

Define tool permissions, input schemas, timeouts, idempotency, retries, human confirmation, and audit requirements. Validate tool results. Never allow a model to assemble and directly execute unrestricted high-risk commands or SQL.

### 8.4 GPU and Video Tasks

Check VRAM, resident models, competition on the same GPU, worker concurrency, queues, priorities, OOM conditions, batching, cancellation, recovery, worker crashes, intermediate artifacts, file cleanup, and GPU utilization.

GPU tasks need resource budgets and scheduling policies. Increasing concurrency alone is not a valid throughput strategy. Evaluate CPU, memory, disk, network, and model-loading overhead together.

---

## 9. Microservices and Service Decomposition

Do not recommend microservices merely because a performance problem exists. First locate the actual constraint among SQL, caching, blocking operations, connection pools, thread pools, single-process limits, file I/O, CPU, GPU, external APIs, and task asynchrony.

Base decomposition on:

- business, data, and transaction boundaries;
- independent release and fault isolation needs;
- resource types and scaling characteristics;
- team structure, operational cost, and network overhead;
- data-consistency and observability cost.

For early-stage and small projects, prefer a modular monolith with independent workers. Commonly appropriate separations include a Web API, general workers, file workers, video workers, AI workers, GPU workers, and a scheduling service.

Standardize trace IDs, error codes, timeouts, retries, idempotency, and versioning across services. Avoid cyclic dependencies and layered retry amplification.

---
