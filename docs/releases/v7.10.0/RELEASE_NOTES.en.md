<!-- Generated from locales/en/docs/releases/v7.10.0/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.10.0 Release Notes

V7.10.0 completes the P1-P2 experience improvements: a base installation without selected optional enhancements is no longer projected as degraded; status and diagnostics identify affected capabilities and provide structured next actions; and the package adds four daily paths, a unified entry, and a read-only `resume` recovery view.

The release also provides explicit UX benchmark collection, whitelist-only aggregate import, and before/after comparison. The benchmark does not start a model or upload data, and it cannot by itself prove faster real Agent tasks.

It also fixes Windows PowerShell 5.1 base installation confusing hidden directories with files during payload copying. Controlled recursive copying now allows the base Marketplace, ten Skills, and native Plugin registration to be read back correctly.

Release, installation, registration, current-task loading, fresh-process acceptance, and Desktop-session effectiveness remain separate evidence layers. Final status comes from this version's workflows, artifact checks, and delivery record.
