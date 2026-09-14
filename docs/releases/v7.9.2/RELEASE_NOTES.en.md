<!-- Generated from locales/en/docs/releases/v7.9.2/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.9.2 Release Notes

Fix `UNREADABLE` from the default capability registry command after Plugin installation. The managed runtime now ships the registry; source checkouts use the authority config and installed layouts use the bundled copy. Explicit `--registry` and fail-closed behavior remain compatible.

Seven isolated regressions cover real packager output, all 25 entries, authority parity, missing files, and corrupt data. This fix does not enable write gates or budget authorization.

Release and account installation evidence comes from this tag's GitHub Actions, release artifacts, and subsequent runtime readback.
