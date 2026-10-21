# V7.17.2 Release Notes

- Replace traceback-only missing-provenance failures and repeated-reply guidance with structured diagnostics and verified recovery from host-observed native locators.
- Scan long chats with bounded backward cursors. Retries and concurrency do not recreate budgets; replacement, corruption and project conflicts remain rejected.
- Detect missing Hook registration and support explicitly selected migration directories verified as the same account location.
- Preserve host trust, authorization, historical accounting and independent review requirements.
- Preflight existing host signing keys. Cache recovery accepts only backups matching the original transaction digest, retains prior failure history and retries missing targets after interruption.
