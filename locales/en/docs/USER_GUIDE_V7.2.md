# V7.2 Operating Guide

Chinese: [`USER_GUIDE_V7.2.md`](USER_GUIDE_V7.2.md)

## V7.2 hardening

- Use Python 3.11 or later. Public CI validates 3.11 and 3.13 on both Windows and Ubuntu.
- `python scripts\validate-package.py` produces package-only evidence and leaves real-host routing as `NOT_EVALUATED`. Repository index and file content must remain unchanged during complete validation, and `--output` must point outside the repository.
- Generate a real-host observation template with `python scripts\routing-eval.py make-host-template`, then use `evaluate-host` to validate eleven fresh independent tasks and their raw final-report digests. Expected Skills must never be copied into observed results.
- Controlled evolution reads evidence required by each signal: model escalation uses actual-model coverage, negative outcomes use terminal-outcome coverage, and unrelated missing fields do not block other signals.
- `$controlled-evolution-governance` is the sole authoritative entry point for controlled-evolution guidance; long-term memory and independent review retain only boundary pointers.

## Four primary domains

V7 retains ten progressively discovered Skills, with four primary domains classified by engineering responsibility rather than implementation language:

- Any-language server applications, APIs, transactions, concurrency, and Workers: `$backend-engineering`
- Browser, WebView, and Renderer work: `$frontend-engineering`
- Models, RAG, agents, AI evaluation, inference, and multimodal generation: `$ai-engineering`
- Databases, middleware, storage, GPU resources, containers, and networks: `$data-middleware-infrastructure`

Six supporting and workflow Skills remain separate: `$log-observability-analysis`, `$engineering-quality-delivery`, `$multi-agent-independent-review`, `$technical-document-writing`, `$long-running-task-memory`, and `$controlled-evolution-governance`.

Use one primary domain and at most two supporting Skills per phase by default. A cross-phase task can change its primary domain instead of loading every domain at once.

## General backend

`backend-engineering` reads shared interface, business, security, transaction, concurrency, job, and resource guidance, then loads one primary stack specialization from project evidence: Java/Spring/JVM, Python Web/async, Node.js, Go, .NET, Rust, or another backend.

Python is no longer coupled to AI. Ordinary Django, FastAPI, Celery, and Python API work uses general backend only. Add AI only when the task actually involves models, RAG, agents, or generation semantics.

## General AI

`ai-engineering` is independent of implementation language and model provider. It covers model calls and streaming, structured output, prompt injection, untrusted output, RAG, embeddings, retrieval access and evaluation, agent tools and confirmation, GPU and multimodal generation state, quality, cost, safety, and observability.

Combine general backend for language SDK, Web API, and Worker mechanics. Combine data infrastructure for vector engines, messaging, object storage, GPU resources, and orchestration.

## V6 to V7 migration

| V6 Skill | V7 route |
|---|---|
| `$java-backend-engineering` | `$backend-engineering` with Java guidance on demand |
| `$python-backend-ai-engineering` | `$backend-engineering` for ordinary server work; `$ai-engineering` for model/RAG/agent work |
| `$data-middleware-ai-infrastructure` | `$data-middleware-infrastructure`; use `$ai-engineering` for AI semantics |
| `$vue-frontend-engineering` | `$frontend-engineering` |

V7 installs no compatibility alias. The installer backs up and removes only managed legacy Skills declared by the Manifest; unknown third-party Skills remain untouched. Discovery of both old and new names after upgrade is a failure.

## Installation readback

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

Upgrade is proven only when the Plugin reports `installed=true`, `enabled=true`, and `version=7.2.0`, all ten new Skills are discoverable, and all four Manifest-declared legacy Skills—including the previously deprecated Vue Skill—are absent.

## Reviewer, lifecycle, and authorization

Reviewer TOML files keep model and effort unset. Automatic selection remains bounded by `luna-low -> luna-medium -> terra-medium -> terra-high`; file count and Skill count do not justify escalation.

V7 retains TaskOutcomeEvent 2.0, `project_id + repo_fingerprint` isolation, signed event chains, delayed SessionEnd sealing, and `execution_authorization=NONE` proposals. Evidence cannot authorize commit, push, deployment, restart, production operations, or data writes. Final delivery reports modified, validated, reviewed, committed, pushed, deployed, restarted, and effective separately.
