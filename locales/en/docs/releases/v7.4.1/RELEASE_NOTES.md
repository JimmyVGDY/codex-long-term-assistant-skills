# V7.4.1 Release Notes

Version: 7.4.1  
Host window: Codex CLI 0.153.0 and the ten preceding stable releases

## Highlights

- Adds a closed eleven-release compatibility registry with pinned official artifacts and evidence profiles.
- Runs Marketplace add, Plugin activation, JSON readback, and removal in an isolated `CODEX_HOME` before account writes.
- Stores schema-3 host bindings for the CLI, registry, capabilities, and payload; drift requires reinstall.
- Preserves unknown Marketplace metadata while managing only this package's fields.
- Handles registered Hook aliases consistently, failing security conflicts closed and returning neutral JSON for Stop variants.
- Gates release on all eleven versions on Windows and Ubuntu.

## Boundaries

The V7.4.0 delegation budget and Terra High automatic ceiling remain unchanged. Future, prerelease, and out-of-window hosts fail closed in Plugin mode. Local isolated evidence is not real-account evidence.
