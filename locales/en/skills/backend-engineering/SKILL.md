---
name: backend-engineering
description: Use for server-side applications, APIs, business logic, authentication and authorization, application transactions, concurrency, jobs, workers, resource lifecycle, or backend reviews across Java, Python, Node.js, Go, .NET, Rust, and other stacks. Identify the actual runtime first. Do not use for pure data/infrastructure, browser-only, or pure model/RAG semantics work.
---

# General Backend Engineering

## Purpose

Use this Skill for server-side application engineering across languages. Shared rules cover interfaces, business boundaries, application transactions, state, concurrency, jobs, security, resources, and validation. Runtime and framework differences load progressively from stack references.

## Minimum loading

1. Read `references/backend-core-rules.md` before substantive analysis or changes.
2. Read `references/backend-stack-routing.md` and identify the language, version, framework, persistence, job system, process, and deployment model from current evidence.
3. Load one primary stack index per independent application:
   - Java, Spring, and JVM: `references/java-backend-rules.md`
   - Python Web, async, and Worker: `references/python-backend-rules.md`
   - Node.js and TypeScript server: `references/nodejs-backend-rules.md`
   - Go server: `references/go-backend-rules.md`
   - .NET server: `references/dotnet-backend-rules.md`
   - Rust, PHP, Ruby, Kotlin, or another server stack: `references/rust-other-backend-rules.md`
4. Split mixed backends and monorepos by directory, process, and deployable unit. Load only the stack relevant to the current subtask.
5. If the stack is uncertain, use only the shared core, disclose assumptions, and do not apply a known framework's lifecycle, transaction, or concurrency semantics to an unknown project.

## Hard boundaries

- Backend owns application success, business rules, server authorization, application transaction orchestration, and job state. Combine `$data-middleware-infrastructure` for SQL/index/DDL, Redis, messaging, search, storage, GPU resources, containers, and networks.
- Combine `$ai-engineering` for model contracts, structured output, prompt safety, RAG, agents, AI evaluation, and generation semantics. Language SDK, Web, and Worker mechanics remain here.
- Use `$frontend-engineering` for browser, WebView, and Renderer state and interaction. Client controls cannot replace server authorization, idempotency, or business rules.
- Do not recommend a rewrite, microservice split, framework upgrade, or stack replacement merely because of performance, maintenance, or language differences.
- Combine `$engineering-quality-delivery` for behavior changes and `$log-observability-analysis` when logs, metrics, traces, or profiles are primary evidence.
- Skill activation does not expand file, Git, deployment, production, or data-write authorization.

## Model and delegation cost

- Prefer Luna Low for file, symbol, configuration, and version location; Luna Medium for bounded null, exception, resource-release, and compatibility scans.
- Use Terra Medium for ordinary business rules and multi-file call chains. Reserve Terra High for access, core state, financial or inventory consistency, complex concurrency, and cross-service consistency.
- Stack detection is candidate evidence only. Split subagents by independent application or evidence domain and do not rescan the same call chain.

## Core principle

> Identify runtime, framework, version, process, and deployment boundaries first. Load the smallest stack-specific guidance, check shared server risks once, and never treat an application transaction as covering an external system.
