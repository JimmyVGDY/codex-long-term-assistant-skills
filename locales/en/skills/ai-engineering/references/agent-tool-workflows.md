# Agents, Tools, and Workflows

Each tool needs minimal input and output schemas, access, idempotency, timeout, cost, rate, error classes, and audit fields. A tool description explains capability; it never grants permission or expands task scope.

Separate reads from writes, reversible from irreversible actions, local from external targets, and test from production. Commit, push, deployment, restart, data writes, messages, paid calls, and publication require authorization immediately before execution. A model plan, historical authorization, or tool availability is not authorization.

Construct high-risk parameters deterministically or through allowlists. Do not execute model-composed Shell, SQL, paths, URLs, or access objects without validation. Validate tool results and handle partial success through explicit compensation or human review.

Bound agent loops by steps, time, tokens or cost, tool count, repeated-action detection, and stop conditions. Long-term state needs an owner, version, and audit trail. Multi-agent workflows define one coordinator, one shared-state writer, disjoint tasks, input baselines, and result schemas; subagents do not inherit additional authority.
