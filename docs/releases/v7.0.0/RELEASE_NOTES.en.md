# V7.0.0 Release Notes

Chinese: [RELEASE_NOTES.md](RELEASE_NOTES.md)

Version: 7.0.0

## Main changes

- Added language-neutral `$backend-engineering` for Node.js, Go, .NET, Rust, and mixed-language services, with Java and Python guidance loaded on demand.
- Added independent `$ai-engineering` for model integration, structured output, RAG, agents, evaluation, inference, and multimodal systems.
- Kept `$frontend-engineering` independent; `$data-middleware-infrastructure` now focuses on databases, middleware, storage, GPU resources, containers, and network runtime boundaries.
- The former Java, Python+AI, and Data+AI Skill names are no longer routable Skills; upgrades remove only the four Manifest-declared legacy directories, including the previously deprecated Vue Skill.
- Synchronized the bilingual responsibility matrix, positive/negative routing cases, Manifest, AGENTS, recovery guide, and release tooling with 7.0.0.
- Added independent Chinese and English documentation sites, repository-wide Markdown link auditing, versioned release evidence, reproducible bilingual artifacts, and a draft-only GitHub Release provenance workflow.

## Unchanged safety boundaries

- `execution_authorization=NONE`
- Skill activation does not expand file, Git, environment, production, or data authority
- No automatic commit, push, publication, deployment, restart, or production write
- Automatic sub-agent ceiling remains `gpt-5.6-terra + high`

## Acceptance boundary

Package validation and the [real Codex implicit-trigger observation](IMPLICIT_TRIGGER_OBSERVATION.en.md) are recorded separately. Four representative implicit-routing scenarios, a source-tree `6.6.0 -> 7.0.0` Plugin upgrade, and fresh-task routing PASS. The public Release ZIP still requires independent provenance and post-download acceptance; this does not establish deterministic selection for every prompt variation.
