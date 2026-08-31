# Evidence Fingerprint and Freshness Protocol

## Goal

Prevent reuse of an old “passed” conclusion after code, configuration, or Git diffs change following a test, review, or approval.

## Fingerprint Inputs

- Git HEAD, branch, and remote;
- staged and unstaged diffs;
- bounded untracked paths and content summaries;
- files relevant to the current functional boundary;
- command, environment, exit code, and result files;
- reviewer packet hash;
- project ID, task ID, and record time.

## States

- `current`: the current repository fingerprint matches the record;
- `stale`: code, configuration, diff, or binding changed, so old evidence cannot prove the current version;
- `failed`: the command actually failed;
- `blocked`: environment or permissions are insufficient;
- `unknown`: evidence is incomplete.

## Mandatory Rules

1. Validation and review evidence must bind to the current project, task, and repository fingerprint.
2. Any change to affected code, public contracts, migrations, or configuration makes related evidence `stale` automatically.
3. After repair following review, the old review packet and affected tests are no longer valid.
4. Preserve pre-existing failures from a full test run separately; a matching fingerprint does not make them ignorable.
5. Evidence proves an action and result. It does not authorize commits, pushes, deployments, restarts, data writes, or production operations.
6. `execution_guard.py validate` and `cp-runtime.py evidence-check` compare evidence with current state; they do not replace the validation itself.
