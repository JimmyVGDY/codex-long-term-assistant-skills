---
name: ai-engineering
description: Use for model or multimodal generation calls, structured output, prompt safety, RAG, embedding and retrieval quality, agent tools, AI evaluation, model routing, cost control, inference workers, or generation recovery across any implementation language or provider. Do not use for ordinary backend logic, pure vector-database operations, or pure GPU/Kubernetes resource work.
---

# General AI Engineering

## Purpose

Use this Skill for language- and provider-independent AI application and inference engineering. Shared rules cover untrusted outputs, contracts, access, state, evaluation, cost, and recovery. Load model integration, RAG, agent, inference, and quality references only when needed.

## Minimum loading

1. Read `references/ai-core-rules.md` before substantive analysis or changes.
2. Load only the relevant specialization:
   - Model calls, streaming, and structured output: `references/model-integration-structured-output.md`
   - RAG, embeddings, retrieval access, and evaluation: `references/rag-retrieval-evaluation.md`
   - Agents, tools, and workflows: `references/agent-tool-workflows.md`
   - Inference Workers, GPU, multimodal, and generation jobs: `references/inference-gpu-multimodal.md`
   - AI quality, safety, cost, and observability: `references/ai-quality-security-observability.md`
3. Establish provider, model version, SDK, sync or async mode, streaming protocol, input/output contract, task state, and deployment from dependencies, configuration, code, and runtime evidence.
4. Split multi-model, multi-provider, and multimodal chains by capability, data, cost, and failure boundary. Do not load unrelated specializations.

## Hard boundaries

- Model output, retrieval, tool arguments, and tool results are untrusted. Programmatically validate money, access, state, code, commands, and external actions; require human approval proportional to risk.
- AI owns model/RAG/agent semantics, evaluation, and generation success. Combine `$backend-engineering` for language SDK, Web API, ordinary Worker, and business transaction mechanics.
- Combine `$data-middleware-infrastructure` for vector engines, storage, messaging, GPU resources, containers, orchestration, and networks.
- Combine `$frontend-engineering` for browser streaming, generation progress, and interaction state.
- A non-empty output is not success. Do not hide contract, access, capacity, or model incompatibility behind unlimited retries, and do not add agents, RAG, vector stores, or GPU merely because a task mentions AI.
- Combine `$engineering-quality-delivery` for behavior changes and `$log-observability-analysis` when logs, traces, model latency, or resource signals are primary evidence.
- Skill activation does not authorize model calls, paid APIs, file changes, Git, deployment, production access, or data writes.

## Model and delegation cost

- Prefer Luna Low for call-site, configuration, model, schema, and state-field location; Luna Medium for bounded output-validation and error-classification checks.
- Use Terra Medium for RAG data flow, agent access, generation state, and ordinary multi-model routing. Reserve Terra High for high-risk tool execution, cross-tenant retrieval, irreversible generation effects, and complex GPU scheduling.
- Do not send unrelated prompts, model outputs, sensitive documents, or full production logs to subagents. Return structured evidence and unverified items.

## Core principle

> Establish model capability, call contract, data and access boundaries first. Define deterministic success, bounded failure, and cost limits before AI output can become business fact or enter an execution path.
