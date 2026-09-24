# V7.13.3 Release Notes

This patch fixes Windows Desktop tasks where ordinary and extended path spellings refer to the same directory but fail to locate an existing budget binding. The product supports Codex Desktop only.

- Recognize Windows path aliases only after filesystem identity proof, reuse existing bindings and ledgers, and preserve historical fingerprints, events, and the first identity proof.
- Serialize binding operations per real task. Conflicting aliases, unavailable identity proof, or disappearing bindings reject the operation rather than creating another root or falling back to an unbound budget.
- Compare verified equivalent lifecycle proofs under the ledger lock. Concurrent or repeated receipts for the same semantic identity retain the first proof digest.
- Apply the same identity rules to external-state and managed-directory checks, protecting the root itself while allowing valid child targets that do not exist yet.
- Retain the Desktop management-component compatibility records from V7.13.2. Frozen V3 remains the default; GPT-5.6 compatibility and comparison remain available. Qualification gates for eighteen evaluation profiles and nine GPT-6 production candidates are unchanged.

The path correction does not establish enforced native dispatch accounting or model qualification. Full validation, installation, native callbacks, public assets, and provenance require separate acceptance. See the [validation record](VALIDATION_REPORT.md) and [inspection record](AUDIT_REPORT.md).
