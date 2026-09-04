# Release automation and artifact provenance

The GitHub Release title is composed from `manifest.json.release_name` and `locales/en/manifest-localization.json.release_name`. Titles must be non-empty strings; whitespace-only values, leading or trailing spaces, control or format characters, overlong values, and generic placeholders fail closed. Length limits are 30 code points for Chinese, 80 for English, and 125 code points or 200 UTF-8 bytes for the combined title; Unicode `Cc`, `Cf`, and `Cs` categories are rejected.

The workflow transports the validated title through a job output and then an environment variable, avoiding direct shell-expression interpolation. A tag run is Draft-only, does not publish automatically, and does not overwrite an existing Release or its assets. Checksums, build witnesses, and GitHub provenance remain separate evidence mechanisms for the bilingual reproducible assets.

The Codex CLI 0.153.2 compatibility boundary is unchanged. The V7.4.4 English title segment is `Versioned Release titles and historical title backfill`; the complete bilingual title is assembled from the two manifest values. Historical Release title backfill is an independent online metadata operation; releases v7.3.0 through v7.4.3 were completed and read back individually, while v7.2.0 and earlier were unchanged.

## Failure handling and rollback boundaries

- If CI fails before a Draft exists, keep the Release absent, diagnose the gate, and use a new commit and patch version when source changes are needed. Do not blindly rerun or automatically move a remote tag.
- If a Draft has incorrect metadata or assets, keep it unpublished and do not clobber it. Correct only auditable metadata; wrong assets or source commits require explicit maintainer approval to delete the draft or issue a new patch version.
- If a tag points to the wrong commit, automation must not force-push, delete, or recreate it. Prefer a new version; never retarget a tag associated with a public Release.
- If a public Release is wrong, do not automatically withdraw it or silently replace binaries. Prefer a corrective release and amendment notice; metadata edits, withdrawal, or deletion require separate authorization and before/after readback.

Commit, push, tag, CI, Draft, public Release, and effective installation remain separate facts during recovery.

## Checklist

- Confirm title sources and all fail-closed constraints.
- Confirm job-output/environment-variable transport.
- Confirm Draft-only and existing-Release no-overwrite behavior.
- Confirm bilingual assets, checksums, witnesses, and provenance separately.
- Confirm Codex CLI 0.153.2 compatibility evidence.
- Obtain online readback before recording historical title backfill as complete.
