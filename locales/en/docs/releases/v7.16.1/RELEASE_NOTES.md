# V7.16.1 Release Notes

This release fixes the child-context Hook rejecting a Codex Desktop parent task or telling it to return incomplete after a large image or other tool result. Previously, a Hook JSON envelope above 2 MiB failed before caller classification.

- Validate complete large events and classify using top-level identity only, ignoring identity-like body content and field ordering.
- Preserve the small-event decoder, 2 MiB child limit and G6/V5 permission checks. Missing, null and empty IDs keep their existing no-child meaning; non-string identities and conflicting nonempty aliases are rejected.
- Never log or spool tool bodies. Bound transport at 128 MiB, parsing at 3 seconds, nesting at 64, value nodes at 262,144, cumulative keys at 1,048,576 characters, retained strings at 65,536 characters and number tokens at 4,096 characters. Resource violations and ambiguous identities fail closed.

Codex Desktop is the only product target. Source/tests, installation readback, live-host effectiveness and public release are separate checks. See the [validation report](VALIDATION_REPORT.md) and [audit report](AUDIT_REPORT.md).
