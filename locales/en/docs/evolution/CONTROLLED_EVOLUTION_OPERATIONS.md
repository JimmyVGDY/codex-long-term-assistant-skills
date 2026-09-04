# V7.4 Controlled Evolution Operations Manual

> Status: `active`. This page applies to V7.4.4. The Evolution component manifest still uses contract version `5.1.0`, and the default policy is `v6.5-default-1`; neither value is the current package version.

## 1. When to Use It

Run evolution analysis only when:

- the task explicitly asks to analyze recurring failures, cost, or process problems;
- a release, milestone, or incident review has been completed;
- at least five records from at least three independent task IDs have accumulated; or
- model tiers, reviewer combinations, or Skill routing need evaluation.

Do not run the complete analysis automatically after every ordinary task. That would add context cost, state noise, and low-value proposals.

## 2. Recommended Workflow

### Step 1: Confirm Project Identity

Confirm that `project_id` matches the current repository, remote, branch, and Project Profile. Stop if any cross-project contamination is detected.

### Step 2: Run a Read-Only Dry Run

```bash
python3 -B scripts/evolution.py run \
  --project-id <project-id> \
  --context-root ~/.codex/project-context \
  --dry-run
```

Check:

- which source files were actually read;
- how many records have no task ID;
- whether the time window is trustworthy;
- whether unrelated historical records were included; and
- whether each signal has enough independent evidence.

Evidence sufficiency is evaluated per signal: dispatch-profile value regression requires outcome and unit-cost samples for adjacent approved profiles, negative outcomes require known terminal outcomes, routing deviation requires explicit routing observations, and Reviewer yield requires attributable results. Missing evidence for one signal does not unconditionally block another signal with sufficient evidence.

### Step 3: Persist Proposals

```bash
python3 -B scripts/evolution.py run \
  --project-id <project-id> \
  --context-root ~/.codex/project-context
```

The runtime does not create another active proposal with the same fingerprint.

### Step 4: Conduct Human Review

For every proposal, check whether:

1. the evidence genuinely supports the problem statement;
2. correlation has been mistaken for causation;
3. the conclusion exceeds its project or version scope;
4. exceptional high-risk cases were omitted;
5. the expected benefit is measurable;
6. the rollback and validation plans are executable; and
7. more data should be collected before changing any rule.

### Step 5: Record the Decision

Use `decide` to record `ACCEPT`, `REJECT`, or `DEFER`:

```bash
python scripts/evolution.py decide \
  --project-id <project-id> \
  --context-root <context-root> \
  --proposal-id <proposal-id> \
  --decision <accept|reject|defer> \
  --actor <human-actor> \
  --rationale "<human rationale of at least ten characters>"
```

### Step 6: Create a Separate Implementation Task

Only after `ACCEPT` may a separately authorized implementation task be created. That task must regenerate its:

- Task Envelope;
- Git baseline;
- modification scope;
- approval;
- Review Packet;
- rollback plan; and
- acceptance criteria.

## 3. Typical Signals and Responses

| Signal | Default response | Prohibited shortcut |
|---|---|---|
| Repeated failures | `MODIFY` candidate | Do not simply add retries or raise the model tier |
| Frequent model escalation | `MODIFY` candidate | Do not make Terra High the default for all tasks |
| Skill-routing deviation | `MODIFY` candidate | Do not load every Skill by default |
| Excessive repair rounds | `MODIFY` candidate | Do not remove the round limit |
| Low reviewer discovery rate | `INVESTIGATE` | Do not remove a reviewer from a small sample |
| Zero reviewer findings over a long window | `DEPRECATE` candidate | First reduce to on-demand use and observe; never delete automatically |
| High non-success rate | `INVESTIGATE` | Do not change global rules before stratifying root causes |

## 4. Data-Quality Problems

Retain an observation but do not generate a modification proposal when:

- the record count is below the policy minimum;
- there are too few independent task IDs;
- only one failure exists;
- the reviewer sample is too small;
- timestamps have no time zone;
- only aggregate totals exist without traceable evidence; or
- a data source is corrupt or its hash chain is invalid.

## 5. Failure Handling

### Corrupt JSONL

Stop analysis, locate the failing line, and restore from a trusted backup or repair the source record. Never skip a bad line and continue.

### Invalid Hash Chain

Stop using the registry and restore it from backup. Preserve the damaged file for audit. Never recompute hashes to conceal historical changes.

### Duplicate Proposal

The runtime returns the existing active proposal. If an earlier proposal was `REJECTED` and materially new evidence now exists, generate a proposal in a new observation window.

### Oversized Data Source

Increase the limit only through controlled policy, or create a redacted aggregate first. Do not allow unbounded project-directory scans.

## 6. Validation Commands

```bash
python scripts/evolution.py validate \
  --project-id <project-id> \
  --context-root <context-root>
```

## 7. Explicit Limitation

The current analysis uses deterministic heuristics, not causal inference. It can identify stable patterns worth investigating or optimizing, but it cannot replace human understanding of business context, implementation details, production risk, and organizational constraints.
