# V4.2 Model Tiers and Workflow Convergence Design

## 1. Optimization Goal

Without removing nine Skills, reducing seven specialist Reviewer responsibilities, or weakening evidence and runtime-isolation constraints, V4.2 reduces:

1. repeated global-prompt content;
2. subagent count, parallelism, and review rounds;
3. repeated loading of parent sessions, complete diffs, logs, and references;
4. use of Terra High or higher models for simple work.

## 2. Core Changes

### 2.1 Global Context

- Compress `global/AGENTS.md` from more than 500 lines to approximately 170.
- Keep domain details in Skill references.
- Retain only cross-project boundaries, authorization, evidence, Skill/model routing, and general delivery globally.

### 2.2 Default Review Budget

| Item | V4.1 Default | V4.2 Default | Compatibility Hard Limit |
|---|---:|---:|---:|
| Agent depth | 3 | 2 | 3 |
| Preimplementation Reviewers | 4 | 2 | 4 |
| Parallel Reviewers | 6 | 3 | 6 |
| Total Reviewers | 12 | 6 | 12 |
| Postimplementation rounds | 3 | 2 | 3 |
| Centralized repair rounds | 3 | 2 | 3 |
| Terra High Reviewers | Unlimited | 1 | 2 |

Hard limits remain for critical production or major migration, but must be raised explicitly at `init`; ordinary tasks do not use them automatically.

### 2.3 Progressive Review Packet

Adds:

- `packet-summary.md`;
- `diff-stat.txt`;
- `name-status.txt`;
- recommended reading order;
- diff bytes and changed-file count;
- workspace `freshness` check.

Reviewers read summary, statistics, and assigned scope first, then related patch hunks when evidence requires. Complete `diff.patch` remains available so token reduction cannot lower evidence quality.

### 2.4 Duplicate-Work Protection

- Do not let the same Reviewer recheck the same packet without reason.
- After a no-findings round on the same packet, do not add rounds mechanically.
- Record the reason for a second opinion on the same packet.
- Rebuild stale packets; do not reuse old conclusions.
- Do not duplicate checkpoints with identical content and Git fingerprint.

### 2.5 Checkpoint Convergence

- Increase the in-progress checkpoint threshold from five to eight substantive actions.
- Load only the latest three checkpoints during recovery by default.
- Reduce the active hot set from 30 to 20 entries.
- Add content fingerprints and skip duplicate appends.
- Persist shared multi-agent checkpoints only at recoverable nodes: plan fixed, consolidation complete, repair complete, and final conclusion—not every dispatch event.

## 3. Typical Flows

### 3.1 Small Task

```text
Main agent identify -> single-agent change/check -> minimum validation -> delivery
```

Default to zero Reviewers. Use one `luna-low` only for clearly valuable independent mechanical verification.

### 3.2 Ordinary Behavioral Change

```text
Main agent Terra -> common packet -> 1–2 Reviewers
  ├─ Luna Medium: compatibility/test evidence
  └─ Terra Medium: function/business
-> consolidate -> centralized repair -> targeted rereview of affected dimensions
```

Default to at most two rounds and six Reviewers total.

### 3.3 High-Risk Change

```text
1–2 preimplementation Reviewers
-> main-agent implementation and targeted validation
-> 2–3 postimplementation Reviewers
  ├─ Luna Medium: baseline scan
  ├─ Terra Medium: specialist judgment
  └─ Terra High: one critical dimension
-> consolidate and repair -> at most 1–2 targeted rereviewers
```

`terra-high` requires a recorded escalation reason; `deep` does not upgrade every Reviewer.

## 4. Quality Protection

| Risk | Protection |
|---|---|
| Fewer Reviewers miss issues | Risk routing, distinct responsibilities, common packet, and explicit hard-limit relaxation when needed |
| Luna lacks business semantics | Progressive escalation; business, data, and concurrency normally permit Terra Medium |
| Summary misses a critical hunk | Keep complete diff; Reviewers may read relevant hunks and direct dependencies |
| Review stops too early | Automatic stop only after no findings on the same packet; changed diffs require a new packet |
| Runtime model cannot be confirmed | Record `unverified`; do not claim platform enforcement |
| Writable parent mislabeled strict read-only | Keep `system-readonly`, `logical-readonly`, and `unknown` distinct |

## 5. Estimation Method

Model names alone cannot predict credits because context, tools, reasoning length, and output vary. Compare using:

- subagent count per task;
- Luna/Terra and Low/Medium/High distribution;
- packet reuse and staleness by round;
- rejected duplicate Reviewer/same-packet attempts;
- actual review and repair rounds;
- characters loaded from global AGENTS, Skills, and references;
- `model_assignment` counts for confirmed, fallback, unverified, and mismatch.

Run five to ten representative low-, medium-, and high-risk tasks, then evaluate cost and miss rate from real Codex usage records.
