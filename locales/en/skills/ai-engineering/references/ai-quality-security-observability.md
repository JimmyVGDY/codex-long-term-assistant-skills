# AI Quality, Safety, Cost, and Observability

Select accuracy, recall, citation, format compliance, safety, refusal, stability, latency, and cost metrics for the capability. Evaluation includes normal, empty, boundary, adversarial, access, unanswerable, long-input, invalid-output, timeout, and fallback cases.

Changes to model, prompt, schema, retrieval, tools, or policy rerun affected evaluation. Offline evaluation, shadow traffic, staged rollout, human sampling, and online metrics are separate evidence layers.

Check direct and indirect prompt injection, exfiltration, tool escalation, corpus poisoning, unsafe rendering, malicious files, and supply chain. A system prompt is not a security boundary; deterministic code enforces access, filtering, schemas, and action confirmation.

Track request volume, tokens, model price, cache, retries, concurrency, queue, GPU time, and failed-call cost. Bound requests and tasks to prevent unbounded context, retry amplification, tool loops, and unnecessary high-cost defaults.

Correlate model, retrieval, tool, Worker, storage, and business state with redacted request, task, and trace IDs. Record versions, state, latency, resource, retries, and error categories without logging secrets, full sensitive prompts or documents, or uncontrolled output.
