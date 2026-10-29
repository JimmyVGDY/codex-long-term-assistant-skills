# V7.17.3 Release Notes

- Distinguish Desktop component updates, confirmed management-contract changes and unavailable probes, while keeping runtime acceptance separate from installation diagnostics.
- Verify the current workspace from a host-registered native turn when first entering a project from a non-Git directory. Partition source v2 and approval cursor v2 by project while preserving old sources, task roots, spending and late-callback ownership.
- Share verified account-root junction handling across parent provenance, child identity and approval binding, fixing false `V5_REPARSE_PATH_DENIED` failures after Windows account migration. Continue rejecting inner links, foreign account directories, file replacements and foreign-project input.
- Fix Windows source read/write and atomic-replacement races and bound long-session scanning. Automatic continuation context cannot provide human approval.
- Advance the frozen internal stable-component contract window to official 0.164.0 and its ten preceding stable releases, with pinned official artifact/source digests. The supported product remains Codex Desktop.

The measured target is Codex Desktop 26.1023.50603 / build 22391 with internal component 0.165.0-alpha.1.2. Listed native reading, approval recovery, cancellation, same-work fallback and account-installation paths were exercised. The pending post-restart client update has not been accepted and no restart was performed. Direct opaque continuation remains denied; the script provides a fresh scoped call on the same work as its safe fallback.

Package validation, independent source review, actual execution and public publication are recorded separately in the [validation report](VALIDATION_REPORT.md) and [audit report](AUDIT_REPORT.md).
