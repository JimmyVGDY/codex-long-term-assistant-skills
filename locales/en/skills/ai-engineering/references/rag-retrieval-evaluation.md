# RAG, Retrieval Access, and Evaluation

Check parsing, chunking, overlap, metadata, language, attachment relationships, embedding model, vector dimension, index version, deletion, and rebuild. Embedding or chunk-strategy changes normally require versioned indexes and rollback-safe rebuilds.

Evaluate keyword, vector, hybrid, filter, TopK, RRF, reranking, MMR, and context assembly as the task requires. Preserve source, version, access, and location for each retrieved fragment; citations must resolve to real evidence.

Enforce tenant, user, project, and document access before or within retrieval. Do not retrieve sensitive content first and rely on a prompt to ignore it. Cache, reranking, query rewriting, and citations keep the same access boundary.

Use versioned real questions, expected evidence, unanswerable items, and access-adversarial cases. Measure retrieval recall, ranking, answer correctness, citation, refusal, latency, and cost. Vector-engine sharding, capacity, backup, and cluster operations are owned by `$data-middleware-infrastructure`.
