# Codex Cross-Project Long-Term Engineering Assistant V6.6 User Guide

## 1. Daily Engineering Work

Describe the task directly. Skills load progressively by stack and phase; ordinary tasks do not trigger full Evolution automatically. Modification, testing, commit, push, deployment, and restart remain separate authorization boundaries.

## 2. Install and Confirm

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

Success requires `installed=true`, `enabled=true`, and `version=6.6.0` together.

## 3. Model Gate and Evidence

```powershell
python scripts\model-gate-acceptance.py --output model-gate-v6.6.json
```

Automatic routing is Luna Low -> Luna Medium -> Terra Medium -> Terra High. Explicit Terra xhigh, Sol, max, and ultra are rejected.

Output is separated into:

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

Codex 0.150.1 rollouts provide diagnostic evidence only. `runtime_model_evidence` may become VERIFIED only when a future host gives Hooks trustworthy attestation that passes correlation, freshness, and signature checks.

## 4. Delayed Automatic Sealing

SessionEnd writes only a signed job and launches a detached worker. The worker later appends `SESSION_ENDED`, validates the complete chain, and creates a detached seal. Manual drain:

```powershell
python scripts\seal-worker.py --queue <project-context>\<project-id>\feedback\seal-queue
```

The queue has pending, running, done, and dead-letter directories. After a worker is terminated, another process can reclaim running jobs whose owning process exited; event IDs and seals remain idempotent.

## 5. Archive, Capacity, and Health Overview

```powershell
python scripts\event-archive.py archive --event-file <task-outcome-v2.jsonl>
python scripts\event-archive.py verify --event-file <task-outcome-v2.jsonl>
python scripts\event-archive.py capacity --project-dir <project-context>\<project-id>
python scripts\event-archive.py health --project-context-root <project-context>
```

Archiving copies closed segments only. It does not move the active file or delete Events, Snapshots, Assessments, or Proposals. Capacity thresholds report or block automatic expansion; they do not clean history automatically.

## 6. Reviewer Calibration

Calibration includes task-difficulty distribution, stable root-cause clusters, repeated-cluster ratio, adoption reasons, regression-prevention claims, and evidence coverage. Missing difficulty, adoption reason, or regression-test reference becomes UNKNOWN, UNSPECIFIED, or insufficient-evidence rather than inferred benefit.

## 7. Safety Boundaries

- Do not rewrite the main-agent model.
- Reviewer TOML does not fix models.
- Automatic flows stop at Terra High.
- Do not accept or implement Proposals automatically.
- Do not commit, push, deploy, restart, or operate production automatically.
- Do not record raw prompts, complete responses, source bodies, diffs, tokens, cookies, API keys, or credentials.
