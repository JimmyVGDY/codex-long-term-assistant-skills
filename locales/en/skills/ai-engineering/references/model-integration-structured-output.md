# Model Integration, Streaming, and Structured Output

Establish model identity, capability, input formats, context and output limits, sampling, region, timeouts, rate and concurrency limits, price, and content policy. SDK defaults do not replace explicit business constraints.

- Prefer native schema or tool protocols and validate locally again.
- Define required fields, types, enums, ranges, lengths, unknown fields, and schema version.
- Bound repair attempts for invalid output and preserve the original error.
- Parsing success still requires access, state, reference, and business validation.
- Evaluate old models, cached output, pending jobs, and consumers when schemas change.

For streaming, verify first event, deltas, completion, errors, cancellation, reconnect, duplicate and order handling, UTF-8 boundaries, structured fragments, and final aggregation. Connection closure is not success without a valid terminal event and complete output.

Provider fallback must account for capability, geography, price, policy, context, schema, and quality. An uncertain result enters reconciliation or human handling rather than blind duplicate paid submission.
