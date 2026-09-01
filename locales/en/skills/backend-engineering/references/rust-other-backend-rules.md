# Rust and Other Backend Stack Rules

For Rust, confirm Edition, MSRV, runtime, Web or RPC framework, features, and deployment target.

- Do not run long blocking I/O or CPU work directly on an async runtime; use bounded blocking execution.
- Inspect Arc scope, Mutex/RwLock held across await, lock order, Channel backpressure, and task cancellation.
- Avoid unconditional `unwrap` or `expect` on production paths. Preserve error sources and map stable external errors.
- Give pools, streams, temporary files, background tasks, and graceful shutdown an explicit owner. Expand review for unsafe, FFI, deserialization, and dynamic loading.

For PHP/Laravel/Symfony, inspect request and container lifetime, queues, ORM, long-running Worker state, and Composer supply chain. For Ruby/Rails, inspect ActiveRecord, transactions, callbacks, process or thread models, job idempotency, and Bundler. For Kotlin/Ktor, inspect coroutine scope, structured concurrency, cancellation, JVM version, and Java compatibility.

For any unsupported stack, read its actual build, framework, entry point, concurrency model, package manager, tests, and deployment evidence. Use `backend-core-rules.md`, disclose unverified stack-specific risks, and never invent framework behavior.
