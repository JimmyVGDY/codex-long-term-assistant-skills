# Postimplementation Review, Consolidation, Centralized Repair, and Targeted Rereview

## 1. Preconditions

Before round one, confirm that the functional boundary is complete; minimum targeted validation ran or its blocker is recorded; the diff is stable; baseline, HEAD, and scope are explicit; isolation and budget are recorded; and the review packet exists with a passing freshness check.

If the workspace changes after packet generation, mark the old packet and its results stale and do not continue dispatching from it.

## 2. Common Review Packet and Progressive Reading

Use `review_packet.py create` to generate:

- `packet-manifest.json`: baseline, HEAD, scope, files, and evidence index;
- `packet-summary.md`: minimum task and validation summary;
- `diff-stat.txt` and `name-status.txt`: low-cost scope assessment;
- `diff.patch`: complete diff, read only when needed.

Reviewer reading order: summary and statistics, assigned hunks, complete context and direct dependencies for changed files, then expansion only when evidence remains insufficient. Do not make every reviewer scan the entire repository, and do not copy complete parent sessions, raw logs, or full tool output into the packet.

## 3. Parallel First Round

Each reviewer receives a unique responsibility, file or call-chain scope, exclusions, packet hash, round and depth, evidence standard, model tier, output schema, and isolation level.

The coordinator waits for all planned reviewers in the round and then consolidates. Do not repair findings one by one as they arrive. Retry a failed reviewer at most once. Redispatching the same reviewer against the same packet requires a second-opinion reason.

Parallelize independent read-only and read-intensive work. Do not give stateful tests, database or middleware operations, environment operations, or shared-document writes to parallel reviewers.

## 4. Consolidation

The coordinator:

1. merges by file, call chain, and business boundary;
2. removes duplicates and groups symptoms with one root cause;
3. distinguishes confirmed, highly likely, speculative, and unverified findings;
4. compares conflicting evidence and avoids another agent when direct adjudication is possible;
5. marks whether the current change introduced each issue;
6. classifies blocking, high, medium, and low findings and defines postrepair validation;
7. produces the minimum complete repair set and order.

At most one specialist second-opinion reviewer may address one dispute. If uncertainty remains, retain it as unverified instead of spawning recursively.

## 5. Centralized Repair and Targeted Rereview

Reviewers do not modify code. After consolidation, the implementation agent completes the minimum repair set in one batch, then:

- inspects the new diff;
- reruns only affected minimum validation;
- regenerates or refreshes the packet;
- rereviews only affected dimensions, normally with no more than two reviewers;
- reuses unchanged evidence by fingerprint instead of repeating equivalent scans.

Expand rereview scope only when public APIs, shared components, global serialization, authorization interceptors, common message models, or shared database fields changed.
