# V7.0 Operating Guide

## Four primary domains

V7 retains ten progressively discovered Skills, with four primary domains classified by engineering responsibility rather than implementation language:

- Any-language server applications, APIs, transactions, concurrency, and Workers: `$backend-engineering`
- Browser, WebView, and Renderer work: `$frontend-engineering`
- Models, RAG, agents, AI evaluation, inference, and multimodal generation: `$ai-engineering`
- Databases, middleware, storage, GPU resources, containers, and networks: `$data-middleware-infrastructure`

Six supporting and workflow Skills remain separate: `$log-observability-analysis`, `$engineering-quality-delivery`, `$multi-agent-independent-review`, `$technical-document-writing`, `$long-running-task-memory`, and `$controlled-evolution-governance`.

Use one primary domain and at most two supporting Skills per phase by default. A cross-phase task can change its primary domain instead of loading every domain at once.

## General backend and AI

`backend-engineering` reads shared server guidance, then loads one primary stack specialization from project evidence: Java/Spring/JVM, Python Web/async, Node.js, Go, .NET, Rust, or another backend. Python is no longer coupled to AI.

`ai-engineering` is independent of implementation language and provider. It covers model calls and streaming, structured output, prompt injection, untrusted output, RAG, retrieval access and evaluation, agent tools, GPU and multimodal task state, quality, cost, safety, and observability.

Combine general backend for SDK, Web API, and Worker mechanics. Combine data infrastructure for vector engines, messaging, storage, GPU resources, and orchestration.

## V6 to V7 migration

| V6 Skill | V7 route |
|---|---|
| `$java-backend-engineering` | `$backend-engineering` with Java guidance on demand |
| `$python-backend-ai-engineering` | `$backend-engineering` for ordinary server work; `$ai-engineering` for model/RAG/agent work |
| `$data-middleware-ai-infrastructure` | `$data-middleware-infrastructure`; use `$ai-engineering` for AI semantics |
| `$vue-frontend-engineering` | `$frontend-engineering` |

V7 installs no compatibility alias. The installer backs up and removes only Manifest-declared managed legacy Skills. Unknown third-party Skills remain untouched.

## Installation readback

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

Upgrade is proven only when the Plugin reports `installed=true`, `enabled=true`, and `version=7.0.0`, all ten new Skills are discoverable, and all four Manifest-declared legacy Skills—including the previously deprecated Vue Skill—are absent.

## Reviewer, lifecycle, and authorization

Automatic model selection remains bounded by `luna-low -> luna-medium -> terra-medium -> terra-high`. V7 retains TaskOutcomeEvent 2.0, `project_id + repo_fingerprint` isolation, signed event chains, delayed SessionEnd sealing, and `execution_authorization=NONE` proposals.

Evidence cannot authorize commit, push, deployment, restart, production operations, or data writes. Final delivery reports modified, validated, reviewed, committed, pushed, deployed, restarted, and effective separately.
