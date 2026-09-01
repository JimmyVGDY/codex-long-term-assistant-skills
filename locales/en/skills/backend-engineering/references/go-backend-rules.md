# Go Server Rules

Confirm the Go version, modules or Workspace, entry points, generated code, and framework. Do not introduce a new framework or elaborate layering for a small change.

- Propagate `context.Context` through requests, databases, and downstream calls; do not store it long term or pass nil.
- Every goroutine needs an owner, exit condition, cancellation, and error convergence. Bound concurrency.
- Define Channel ownership, closure, capacity, backpressure, and blocking behavior. Check WaitGroup pairing, copied locks, lock order, races, and loop-variable capture.
- Reuse configured HTTP clients, set deadlines and limits, close response bodies, and retry only with idempotency. Close Rows, statements, transactions, files, archives, and temporary resources.
- Preserve error chains and use `errors.Is/As`; avoid string matching and internal error leakage.
- Interfaces belong at real variation seams, not around every structure. Run relevant tests and race checks for concurrency changes; use benchmarks or runtime evidence for performance claims.
