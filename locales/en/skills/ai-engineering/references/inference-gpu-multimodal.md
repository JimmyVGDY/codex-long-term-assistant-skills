# Inference Workers, GPU, and Multimodal Generation

Image, audio, video, and long inference work use durable business state that distinguishes submitted, running, waiting for resources, cancelling, complete, failed, uncertain, and reconciliation-required. Completion validates terminal state, artifact, ownership, persistence, and business checks together.

Track input, model, parameters, seed, references, output, and intermediate artifacts. Define cleanup or retention for temporary files, storage objects, charges, and provider jobs on failure, cancellation, and timeout.

Inspect model residency, load time, memory, same-device contention, Worker count, batching, priorities, queues, OOM, fragmentation, cancellation, recovery, and crashes. Before increasing concurrency, account for CPU, RAM, disk, network, model load, and downstream storage.

This Skill owns AI semantics, quality, and recovery. `$data-middleware-infrastructure` owns GPU quotas, device mapping, containers, orchestration, drivers, and cluster scheduling. `$backend-engineering` owns Worker runtime and language concurrency.

Do not split services merely because work uses AI or GPU. Use data and transaction ownership, resource type, failure isolation, release independence, and operational cost as the seam.
