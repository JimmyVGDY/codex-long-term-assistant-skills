<!-- Generated from locales/en/docs/releases/v7.5.1/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.5.1 Release Notes

Correct the concurrent acceptance timing assumption: retry a bounded two-second lock timeout after the other call finishes, and verify a single committed transaction. Add forced-contention coverage for unchanged watermarks and idempotent worker recovery. The lock bound and runtime watermark protocol retain their existing contract.

Theme: task feedback and measured optimization benefits.

- Fix Profile/Hook repository fingerprint disagreement and unify default/explicit policy.
- Add task binding, structured validation evidence and parent-finalized feedback; Stop links reports while preserving host terminal fields.
- Check identity, policy, seals, coverage and freshness before analysis. Explicit opt-in enables incremental, cooled-down analysis and idempotent recovery.
- Freeze testable proposal hypotheses. Separate implementation validation from observed benefit, revalidate references on replay, and cover cancellation, rollback and terminal states.
- Verify each calibration sample against its own ledger; compare matching scenarios within one project/repository using independent-task weights and uncertainty.
- Generate pending regression candidates and recurrence follow-ups from confirmed causes, retaining execution_authorization=NONE.

The frozen Codex CLI 0.153.4 plus ten preceding stable-release window is retained; no broader host support is claimed. Automation defaults to disabled. Historical event/proposal hashes remain unchanged. Analysis without valid project identity now returns a blocked state.

See the [validation report](VALIDATION_REPORT.en.md) and [audit report](AUDIT_REPORT.en.md) for delivery evidence.
