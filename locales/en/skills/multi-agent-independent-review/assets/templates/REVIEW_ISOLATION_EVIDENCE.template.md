# Reviewer Runtime Isolation Evidence

- Feature boundary:
- Recorded at:
- Coordinating Agent:
- Reviewer Agent type:
- Actual Agent configuration path:
- Reviewer TOML declaration:
- Actual parent-session sandbox:
- Subagent runtime permission information:
- Confirmed use of the specified Agent:
- Controlled probe executed:
- Probe result: not-run / sandbox-denied / permission-denied / write-succeeded / invalid
- Probe environment: disposable test repository / not applicable
- Evidence summary:

## Isolation Level

- [ ] Level A: system-isolated review (system-readonly)
- [ ] Level B: behaviorally read-only review (logical-readonly)
- [ ] Level C: implementation Agent self-review (self-review)
- [ ] Unverified (unknown)

## Strict Read-Only Eligibility

- Eligible:
- Basis:
- Limitations and unverified items:

> A `sandbox_mode = "read-only"` declaration alone does not prove system isolation. A controlled write probe may run only in a disposable test repository; it must never run automatically in a real project or production environment.
