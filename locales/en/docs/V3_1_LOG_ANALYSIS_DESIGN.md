# v3.1 Design: Log and Observability Analysis Skill

## 1. Goal

v3.1 extracts log analysis from scattered supporting checks in technical Skills into an independent, automatically routable cross-cutting workflow while preserving domain responsibilities and permission boundaries.

Core role:

> Orchestrate log and observability analysis across environments and stacks. Domain Skills explain mechanisms; quality delivery loads only when work enters modification and delivery.

## 2. Why It Is an Independent Skill

Logs may come from local files, uploaded archives, development/test environments, remote services, production containers, Kubernetes, Java/Python applications, databases, and middleware. They share a method:

```text
Confirm scope and time zone
    -> Inventory and completeness
    -> Cluster anomalies
    -> Cross-source timeline
    -> Grade evidence and candidate root causes
    -> Low-risk validation steps
```

Putting this only under production operations or one technology would make the scope too narrow or duplicate responsibilities.

## 3. Responsibilities

| Module | Responsible For | Not Responsible For |
|---|---|---|
| `log-observability-analysis` | Inputs, scope, timelines, clustering, evidence, validation, and read-only modes | Every Java/Python/database rule, code changes, or deployment |
| Java/Python/data Skills | Concrete stacks, threads, transactions, workers, middleware, and infrastructure mechanisms | General log orchestration |
| `engineering-quality-delivery` | Gates after transition to changes, tests, Git, and environment operations | Ordinary read-only log analysis |
| `long-running-task-memory` | Checkpoints for multiround or cross-session diagnosis | One-time single-file analysis |
| `technical-document-writing` | Formal incident reports and postmortems | Raw log analysis itself |

## 4. Four Execution Modes

1. **Static files**: bounded decompression, chunked reading, and temporary parsing without overwriting originals.
2. **Local runtime**: inspect local processes, containers, and logs; writes separately authorized.
3. **Remote nonproduction read-only**: limit scans and query cost; nonproduction does not imply write permission.
4. **Production read-only**: strict limits on time, lines, files, and query cost; no modification, cleaning, restart, deployment, traffic switching, or data writes.

## 5. Multi-Agent Boundary

The Skill supports but does not default to multiple agents:

- The main agent handles ordinary single-file, single-service tasks.
- For many services, components, or a long timeline, parallelize by application, database, middleware, infrastructure, security, or timeline.
- Subagents remain read-only and return structured results.
- The main agent normalizes time zones, deduplicates, resolves conflict, and consolidates evidence.
- A log-analysis subagent is not a code Reviewer and does not trigger code review automatically.

## 6. Security and Resources

- Logs may contain private data, secrets, log injection, and external input.
- Stream large files and cap archive file count, size, and expansion ratio.
- Production read-only commands still consume CPU, disk, network, and database capacity.
- Missing, sampled, out-of-order logs and clock drift constrain conclusions.
- Temporal correlation is not causal proof.

## 7. Progressive Loading

`SKILL.md` retains triggers, mandatory steps, four modes, and composition boundaries. Complete flows live in `references/`, and report templates in `assets/`, following progressive Skill loading without persistent prompt bloat.
