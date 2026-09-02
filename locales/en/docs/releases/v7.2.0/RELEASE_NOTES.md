# V7.2.0 Release Notes

Chinese: [RELEASE_NOTES.md](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/v7.2.0/RELEASE_NOTES/)

Version: 7.2.0

## Key changes

- Python 3.11 is now the minimum. Windows and Ubuntu CI both cover Python 3.11 and 3.13, while the installer and complete validator fail closed on older interpreters.
- Complete validation now snapshots the Git index, tracked and untracked content digests, deletions, link types, and interrupt paths before and after execution; validation output must be outside the repository.
- Controlled evolution checks evidence by signal type: model escalation requires actual-model coverage, negative outcomes require terminal-outcome coverage, and unrelated missing telemetry no longer blocks other signals. Coverage is calculated over unique `task_id` values.
- Eleven real Codex host-routing scenarios now verify Plugin installation and enablement, fresh independent tasks, prompts without explicit Skill names, and byte-count/SHA-256 binding of final reports. The result explicitly does not claim a host-signed internal router trace.
- The installer supports Codex CLI 0.152.1's strict local Marketplace schema by removing known-incompatible top-level `owner/interface` fields while preserving unknown external metadata.
- `long-running-task-memory` and `multi-agent-independent-review` no longer duplicate controlled-evolution guidance; both route to `controlled-evolution-governance` as the single authoritative entry point.

## Unchanged safety boundaries

- `execution_authorization=NONE`
- Plugin installation still fails closed on unverified Codex CLI versions
- Skill activation does not expand file, Git, environment, production, or data authority
- The automatic sub-agent ceiling remains `gpt-5.6-terra + high`

## Acceptance boundary

Package routing regression proves only static cases and tool contracts and records `routing_host_observation=NOT_EVALUATED`. Real-host acceptance, complete local installation, remote publication, and post-download artifact verification are recorded separately; a PASS at one stage does not substitute for readback at another.
