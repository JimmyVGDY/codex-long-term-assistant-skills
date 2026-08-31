---
name: multi-agent-independent-review
description: Use for risk-based design gates and independent functional, compatibility, security, performance, contract, concurrency, and delivery reviews.
---

# Independent Multi-Agent Review

1. Select execution profile, Reviewer cost tier, and model profile independently.
2. Automatic routing follows `luna-low -> luna-medium -> terra-medium -> terra-high`; the ceiling is Terra High. Sol, `xhigh`, `max`, and `ultra` are forbidden for automatic dispatch.
3. Bind every Review Packet to Project ID, Task ID, Git baseline, Task Envelope, packet hash, validation summary, and assigned scope.
4. Read summary and statistics first, then assigned diff and direct dependencies, then expand only when evidence remains insufficient.
5. Collect one round before deduplication, root-cause clustering, conflict resolution, and centralized repair.
6. After repair, refresh only affected evidence and packet content. Stop repeated review when the packet is unchanged or no new information exists.
7. Defaults: parallel <=3, cumulative <=6, post-implementation rounds <=2, repair rounds <=2, Terra High reviewers <=1.

Independent context is not system read-only. A writable parent without sandbox-denial evidence supports only `logical-readonly`. Review evidence never authorizes modification, commit, push, deployment, restart, or production operation.
