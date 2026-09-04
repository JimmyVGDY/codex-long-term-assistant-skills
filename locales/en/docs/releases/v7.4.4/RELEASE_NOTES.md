# V7.4.4 Release Notes

Version: 7.4.4
Theme: Versioned Release titles and historical title backfill

The GitHub Release title is composed from the validated Chinese value in `manifest.json.release_name` and the English value in `locales/en/manifest-localization.json.release_name`. The English title is `Versioned Release titles and historical title backfill`.

Title metadata must be a non-empty string. Whitespace-only values, leading or trailing spaces, control or format characters, overlong values, and generic placeholder titles fail closed. The workflow passes the title through a job output and then an environment variable, avoiding direct shell-expression interpolation.

Length limits are 30 code points for Chinese, 80 code points for English, and 125 code points or 200 UTF-8 bytes for the combined title; Unicode `Cc`, `Cf`, and `Cs` category characters are rejected.

The workflow is Draft-only, does not publish automatically, and does not overwrite an existing Release or its assets. Reproducible bilingual assets, checksums, build witnesses, and GitHub provenance remain separate evidence mechanisms. The Codex CLI 0.153.2 compatibility boundary is unchanged.

Historical title backfill is an independent online metadata operation. Releases v7.3.0, v7.4.0, v7.4.1, v7.4.2, and v7.4.3 were backfilled and read back individually; v7.2.0 and earlier were unchanged. All five before/after checks confirmed that `body_sha256`, assets, draft, prerelease, and published_at were unchanged. Per-release IDs, before/after titles, and preserved-field hashes are recorded in [`HISTORICAL_RELEASE_BACKFILL.json`](HISTORICAL_RELEASE_BACKFILL.json). Local package-only validation and logical-readonly independent review passed; remote CI, tag, Draft, and public Release readback remain pending, and no real-account installation was run.
