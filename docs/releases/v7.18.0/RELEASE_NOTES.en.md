<!-- Generated from locales/en/docs/releases/v7.18.0/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.18.0 Release Notes

- Healthy base installations can be run again safely. The installer checks plugin identity, version and activation, and preserves user files during recovery.
- Projects can temporarily adjust gate wait, backoff and retry settings. The assistant reconciles the original operation when a write result is unknown. Tasks and late receipts retain their ledger after a verified account-directory move.
- Projects opting into the model catalog can select GPT-6.2 Sol and Astra according to host capability, task fit and budget. A rollback applies to subsequent new tasks.
- Release signing requires matching Windows and Ubuntu archives for both locales. Reruns reconcile the tag commit and six assets before accepting an existing release, preserving incomplete drafts for inspection.

See the [validation report](VALIDATION_REPORT.en.md) and [audit report](AUDIT_REPORT.en.md) for evidence and coverage.
