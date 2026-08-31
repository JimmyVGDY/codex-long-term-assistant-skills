# Approval, Evidence, and Finalization

## 1. Three Object Types

| Object | Answers | Does Not Answer |
|---|---|---|
| Approval | Whether the current action has explicit, still-valid authorization | Whether the action succeeded |
| Evidence | What a validation, review, or readback observed | Whether another action is allowed |
| Finalization | Whether current facts support a final claim | It neither performs actions nor replaces acceptance |

## 2. Approval

An Approval binds at least:

- Approval ID;
- project ID;
- task ID;
- operation;
- `local`, `nonproduction`, or `production` environment;
- current repository baseline SHA-256;
- issue time and absolute expiration;
- single-use consumption state.

### 2.1 Record Explicit Authorization

After the upper workflow has obtained explicit authorization:

```bash
python3 scripts/cp-runtime.py approval-issue \
  --output /external/approvals/APR-001.json \
  --approval-id APR-001 \
  --profile /external/project/project-profile.json \
  --task-id TASK-001 \
  --operation commit \
  --environment local \
  --repo-path /path/to/repo \
  --ttl-minutes 30 \
  --approved-by requester
```

This record provides auditable integrity. It is not a digital signature and cannot defend against a malicious actor with equivalent file-write access.

### 2.2 Consume Before the Action

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py authorize-action \
  --state-dir /external/task/TASK-001 \
  --action committed \
  --approval /external/approvals/APR-001.json
```

If repository code changes before the action, baseline mismatch invalidates the Approval.

### 2.3 Read Back After the Action

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py record-action \
  --state-dir /external/task/TASK-001 \
  --action committed \
  --status success \
  --evidence "git rev-parse HEAD = ..."
```

`record-action` does not commit. It records actual readback after an external action completes.

## 3. Evidence Freshness

```bash
python3 scripts/cp-runtime.py evidence-record \
  --output /external/evidence/EV-001.json \
  --evidence-id EV-001 \
  --profile /external/project/project-profile.json \
  --task-id TASK-001 \
  --repo-path /path/to/repo \
  --kind validation \
  --status valid \
  --source "mvn test" \
  --summary "Targeted tests passed"
```

After code, the staging area, or untracked files change, Evidence Freshness returns `STALE`, and the record no longer validates the current baseline.

## 4. Finalization Integrity

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py finalize \
  --state-dir /external/task/TASK-001 \
  --claim modified \
  --claim validated \
  --claim committed \
  --output-json /external/task/TASK-001/finalization.json \
  --output-markdown /external/task/TASK-001/finalization.md \
  --require-all
```

Supported claims:

```text
modified
validated
reviewed
committed
pushed
deployed
restarted
effective
```

A claim without current evidence is `BLOCKED`:

- `committed` is based on a change between initial and current HEAD.
- `pushed` requires action readback or a local upstream reference; the latter explicitly retains the limitation “remote not read over the network.”
- `deployed`, `restarted`, and `effective` require explicit action readback.
- Text scanning and state records do not replace actual platform state.
