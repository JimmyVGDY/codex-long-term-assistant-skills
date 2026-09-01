# Data Contracts, Relational Databases, Transactions, and Migrations

## 1. Interface, Data, and Contract Compatibility

Whenever APIs, databases, messages, caches, files, or serialization are involved, contract compatibility must be checked.

Without explicit authorization, do not:

- remove an existing field or change its meaning, type, or default value;
- change existing enums, states, error codes, or exception semantics;
- change message formats, Redis keys, object keys, or serialization formats;
- break historical data, legacy callers, legacy frontends, legacy workers, or older instances;
- create bidirectional incompatibility that prevents old and new versions from coexisting during a staged rollout.

New fields should be ignorable by older callers. Message consumers, cache deserialization, and database migrations must account for old and new formats coexisting.

Every contract change must state:

- producers, consumers, and data owners;
- the compatibility window between old and new versions;
- defaults and fallback behavior;
- data migration, rollback, and cleanup plans;
- staged-rollout and monitoring metrics.

---

## 2. Databases and SQL

### 2.1 Queries and Indexes

Proactively check:

- index usage, leftmost-prefix matching for composite indexes, and covering indexes;
- table lookups, full-table scans, filesorts, and temporary tables;
- deep pagination, N+1 access, correlated subqueries, and duplicate queries;
- batch operations, unique constraints, and idempotency;
- data skew, statistics, and execution plans;
- primary-replica lag and read/write consistency.

When proposing SQL, state the recommended index, column order, estimated affected rows, lock scope, execution-plan validation, rollback method, and whether direct production execution is appropriate.

Do not add indexes blindly because they “might be faster.” Evaluate write amplification, storage cost, selectivity, and redundancy with existing indexes.

### 2.2 Transactions, Locks, and Consistency

Check isolation levels, row locks, gap locks, deadlocks, lock waits, long transactions, transaction retries, and cross-system consistency.

Do not keep database transactions open around long external calls, file processing, or human waits. For critical writes, prefer database unique constraints, version columns, conditional state updates, and controlled retries to enforce idempotency.

For read-before-write flows, check for races. Use the following when appropriate:

- unique constraints;
- conditional updates;
- optimistic locking;
- pessimistic locking;
- idempotency tables;
- the Outbox pattern or another eventual-consistency design.

### 2.3 DDL and Data Migrations

Evaluate table locks, table rebuilds, online DDL, coexistence of old and new code, backfills, replication, and disk space.

For large-table changes, prefer this staged sequence:

1. Add a compatible structure.
2. Release compatible code.
3. Backfill in batches.
4. Switch reads and writes.
5. Verify and observe.
6. Remove the old structure last.

Never modify an already-applied historical migration; add an incremental migration instead. Backfills must support rate limits, retries, checkpoints, auditing, and compensation.

---
