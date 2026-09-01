# General AI Engineering Core Rules

## Capability, data, and success

Identify whether the capability is text, image, audio, or video generation, embedding, retrieval, classification, ranking, agent work, inference, or training assistance. Establish provider, model, region, quota, pricing, input/output limits, and data-processing boundary.

Define deterministic success across provider acceptance, complete and valid output, trustworthy terminal state, readable owned artifacts, persistence, billing, audit, citations, and business state. HTTP 200, a provider task ID, a non-empty output, or an existing file does not alone prove completion.

## Untrusted output

Treat model output, retrieved content, citations, tool arguments, and tool returns as untrusted. Apply schema, type, enum, length, range, access, state, cross-field, reference, policy, and business validation as risk requires. Never let unvalidated AI output directly change access, money, inventory, state, audit facts, commands, SQL, paths, or the only copy of source data.

## Timeout, retry, idempotency, and recovery

Separate explicit failure, retryable failure, throttling, capacity, content rejection, invalid parameters or model, and uncertain transport outcome. Bound attempts, backoff, jitter, total time, idempotency, and stop conditions.

Durable generation state includes business task ID, provider task ID, model and parameter version, state, phase, progress, retry, error, cancellation, input/output references, and timestamps. Reconcile and recover after process restart instead of relying only on in-memory polling.

## Privacy, access, and versioning

Classify prompts, attachments, retrieval documents, outputs, logs, and cache. Minimize external disclosure and redact secrets and sensitive fields. Keep tenant and object access across retrieval, cache, sessions, vectors, artifacts, and task queries.

Version models, providers, regions, prompt templates, schemas, sampling, tools, embeddings, indexes, and evaluation sets. Any relevant change invalidates affected evaluation and acceptance evidence.
