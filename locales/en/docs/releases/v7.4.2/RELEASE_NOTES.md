# V7.4.2 Release Notes

Version: 7.4.2  
Host window: Codex CLI 0.153.2 plus the ten preceding stable releases

## Codex 0.153.1 / 0.153.2 changes

- 0.153.1 makes Guardian computer-use scoring obey the active model's `node_repl_auto_review_required` policy and invalidates stale scores when the model changes.
- 0.153.1 adds API-supported but default-hidden GPT-6-Astra catalog entries and a `unified_exec` interface. Neither the default model, the model picker, nor this package's automatic routing changes as a result.
- 0.153.2 only updates the Fast-tier description from 1.5x to 2x. It introduces no new Plugin, Hook, or configuration contract.

## Package adaptation

- Advances the closed registry anchor to 0.153.2 and freezes `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, `0.151.0`, `0.150.1`, `0.150.0`, `0.149.1`, `0.149.0`, and `0.148.0`.
- Pins the official tarball, SRI, SHA-256, CLI-help, and Plugin-JSON evidence for 0.153.1/0.153.2. Versions 0.147.0/0.146.1 remain only in immutable V7.4.1 historical evidence.
- Adds regressions for model-switch evidence invalidation and for ensuring `unified_exec` does not consume sub-agent dispatch permits or budget.
- Updates the installer, bilingual manifests, reproducible build, validators, and Windows/Ubuntu eleven-cell workflow to V7.4.2.

## Unchanged boundaries

- GPT-6-Astra is not enabled automatically. Luna/Terra routing, weights, the Terra High ceiling, and proposal `execution_authorization=NONE` remain unchanged.
- `unified_exec` is not a sub-agent dispatch entry point. Actual `spawn_agent` calls still require an explicit permit and root-task budget gate.
- Ordinary Hook fields are not trusted runtime-model evidence. Future, prerelease, and out-of-window hosts remain fail-closed.

## Current evidence status

Windows isolated CLI, Plugin round-trip, synthetic Hook, and official-artifact checks pass for 0.153.1 and 0.153.2. The complete eleven-cell run, Ubuntu CI, real-account acceptance, independent review, tag, and public Release require separate readback in the final validation report.
