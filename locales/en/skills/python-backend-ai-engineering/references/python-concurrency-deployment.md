# Synchronous and Asynchronous Code, the GIL, Multiprocessing, and Deployment

## 4. Synchronous, Asynchronous, and Blocking Models

Do not assume a system has high concurrency merely because it uses `async def`. Inspect the complete call chain:

- whether database and HTTP clients are asynchronous;
- whether file I/O, third-party SDKs, and model calls block;
- whether image, video, serialization, or algorithmic work is CPU-bound;
- whether synchronous locks, `time.sleep`, or cross-thread async objects are used.

Calling a synchronous database driver, `requests`, large synchronous file I/O, heavy PIL computation, blocking FFmpeg waits, or CPU-bound algorithms directly on the event loop can block every request.

Use these principles:

- use asynchronous clients for asynchronous I/O;
- place short blocking work in a bounded thread pool;
- use multiprocessing or independent workers for CPU-bound work;
- use a reliable task queue for long-running tasks;
- use independent GPU workers for GPU tasks.

Do not use `asyncio.gather`, thread pools, process pools, or background tasks without bounds. Define concurrency limits, timeouts, cancellation, exception collection, and resource cleanup.

---

## 5. Multiprocessing, Multithreading, and the GIL

When analyzing performance, distinguish I/O-bound, CPU-bound, GPU-bound, and mixed workloads.

### 5.1 I/O-Bound Work

Consider asynchronous I/O, bounded thread pools, multiple web workers, and connection pools, while accounting for downstream capacity and aggregate connections across workers.

### 5.2 CPU-Bound Work

Do not expect linear scaling from multiple threads in one process. Prefer multiprocessing, an independent compute service, NumPy, native libraries, or C/C++ extensions.

### 5.3 GPU-Bound Work

Check resident models, VRAM, competition on the same GPU, worker count, OOM conditions, batching, task priorities, multi-GPU allocation, cancellation, and recovery.

Do not blame “Python performance” generically. Locate the actual constraint in the interpreter, GIL, database, network, file I/O, algorithm, serialization, SDK, model, GPU, or service architecture.

---

## 6. Web Service Deployment

Do not run production solely on a development server. Evaluate Uvicorn, Gunicorn, Uvicorn workers, Hypercorn, Nginx, Docker, and Kubernetes according to the project.

Check:

- worker count and memory per worker;
- request timeouts, Keep-Alive, maximum request bodies, and upload limits;
- graceful shutdown, health checks, and readiness checks;
- logging, aggregate connection-pool size, and multi-instance load balancing.

Do not apply a worker-count formula mechanically. Consider CPU, memory, request type, I/O ratio, connection limits, downstream rate limits, and the proportion of CPU-bound work.

Under multiprocessing, each worker normally has its own memory, connection pools, models, local caches, and global variables. Adding workers increases both memory consumption and connection count.

---
