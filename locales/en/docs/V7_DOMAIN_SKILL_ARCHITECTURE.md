# V7 General Domain Skill Architecture and Routing Matrix

## Goal

V7 classifies primary Skills by engineering responsibility rather than implementation language:

```text
backend-engineering
frontend-engineering
ai-engineering
data-middleware-infrastructure
```

Languages, frameworks, model providers, and infrastructure products become progressively loaded references. The same four primary domains cover the existing Java, Python, and Web stacks while adding Node.js, Go, .NET, Rust, PHP, Ruby, and future backends without adding a new top-level Skill for every language.

## Responsibility matrix

| Primary Skill | Owns | Loads progressively | Does not own |
|---|---|---|---|
| `backend-engineering` | Server interfaces, business layers, authentication and authorization, application transaction semantics, concurrency, jobs, resilience, resource lifecycle, and server testing | Java/Spring/JVM, Python Web/async, Node.js, Go, .NET, Rust, and other server stacks | Browser interaction; database-engine, broker, or platform operations; model quality and RAG evaluation |
| `frontend-engineering` | Browser, WebView, Renderer, state, routing, forms, async races, security, performance, build, and interaction validation | Web frameworks, legacy pages, microfrontends, and hybrid Renderer stacks | Pure server, data, or inference work; desktop main process and native system capability |
| `ai-engineering` | Model contracts, structured output, prompt safety, RAG, agent tools, evaluation, cost, fallback, generation state, and recovery | Hosted models, private inference, RAG, agents, GPU/multimodal, and AI quality | Ordinary server business logic; database/vector-engine operations; GPU/Kubernetes resource provisioning |
| `data-middleware-infrastructure` | Databases, locks, Redis, messaging, search/vector storage, files/object storage, GPU resources, containers, orchestration, and networks | Component-specific data, middleware, storage, runtime, and capacity guidance | Ordinary application logic, browser interaction, model correctness, and prompt/RAG semantics |

## Seam decisions

| Scenario | Primary | Optional support | Decision |
|---|---|---|---|
| ORM Session, application transaction, endpoint idempotency | `backend-engineering` | `data-middleware-infrastructure` | Application success is backend; SQL, locking, and engine mechanics are data infrastructure |
| SQL, indexes, DDL, database locks, migration execution | `data-middleware-infrastructure` | `backend-engineering` | The data engine is primary; load backend only to trace application callers |
| Model API, structured output, prompt injection, fallback | `ai-engineering` | `backend-engineering` | Model behavior and trust are primary; HTTP and application state are backend support |
| RAG recall, access filtering, citations, evaluation | `ai-engineering` | `data-middleware-infrastructure` | Retrieval semantics and access are AI; vector capacity and index operations are infrastructure |
| GPU Worker state, cancellation, and recovery | `ai-engineering` | `backend-engineering`, `data-middleware-infrastructure` | AI owns task semantics; backend owns Worker runtime; infrastructure owns device capacity |
| AI streaming UI, progress, and interaction races | `frontend-engineering` | `ai-engineering`, `backend-engineering` | Browser state is primary; model and server contracts support the chain |

Keep one primary domain Skill per phase and at most two supporting Skills by default. A cross-phase task may change its primary Skill rather than loading every domain for the entire task.

## Backend progressive loading

`backend-engineering` reads shared core guidance, then loads at most one primary stack reference for each independent application: Java/Spring/JVM, Python Web/async/Worker, Node.js server, Go server, .NET server, Rust server, or an evidence-based fallback for other stacks. Mixed repositories are split by directory, process, and deployable before loading stack guidance.

If the stack cannot be confirmed, use only the shared core, state what remains unverified, and never force a known framework lifecycle onto an unknown project.

## AI progressive loading

`ai-engineering` keeps cross-language rules in its core and loads model integration, RAG, agents, GPU/multimodal inference, or AI quality and observability as needed. Language SDK, exception, concurrency, and resource behavior remains in the applicable backend stack. Vector engines, storage, GPU devices, containers, and clusters remain data-infrastructure responsibilities.

## Positive and negative routing baseline

`backend-engineering` should route Spring transactions, FastAPI async chains, Fastify middleware, Gin context, ASP.NET Core DI, Axum shared state, mixed-language service boundaries, and language-neutral server design. It should not route pure SQL plans, broker operations, Kubernetes capacity, browser components, or pure prompt and RAG evaluation.

`ai-engineering` should route model calls, schemas, prompt injection, RAG, agents, evaluation, tokens, fallback, inference, and multimodal generation state. It should not route ordinary backend tasks without model behavior, pure vector/GPU cluster operations, or a task merely because the project name contains AI.

## Upgrade policy

V7 installs no compatibility alias. Upgrade first backs up and then removes these managed legacy directories before installing the new Skills:

- `java-backend-engineering`
- `python-backend-ai-engineering`
- `data-middleware-ai-infrastructure`
- `vue-frontend-engineering`

Unknown third-party Skills remain untouched. Validation fails closed when a managed legacy directory remains, old and new Skills are both discoverable, or a new Skill is missing.

## Acceptance

1. Chinese and English packages expose exactly ten unique Skills with the same four primary domains.
2. The three replaced domain Skills do not remain in source, Plugin payload, or installed discovery.
3. Java and Python guidance remains discoverable as backend stack references.
4. Node.js, Go, .NET, Rust, mixed backend, pure AI, and AI+GPU routing cases pass.
5. Bilingual, semantic, package, install/restore, and deterministic release validation passes.
6. Real Codex implicit-routing observation runs last; package regression alone is not host evidence.
