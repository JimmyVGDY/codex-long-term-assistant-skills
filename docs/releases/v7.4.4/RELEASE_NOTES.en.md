# V7.4.4 Release Notes

Version: 7.4.4
Theme: Versioned Release titles and historical title backfill

## Release title

The GitHub Release title is composed from `manifest.json.release_name` and `locales/en/manifest-localization.json.release_name`:

- Chinese: the validated value of `manifest.json.release_name`
- English: `Versioned Release titles and historical title backfill`

Title metadata must be a non-empty string. Whitespace-only values, leading or trailing spaces, control or format characters, overlong values, and generic placeholder titles are rejected; any violation fails closed. The workflow passes the title through a job output and then an environment variable, avoiding direct shell-expression interpolation.

Length limits are 30 code points for Chinese, 80 code points for English, and 125 code points or 200 UTF-8 bytes for the combined title; Unicode `Cc`, `Cf`, and `Cs` category characters are rejected.

## Release boundaries

- The workflow creates only a maintainer-review Draft Release; it does not publish automatically.
- If a Release already exists for the target tag, creation is skipped and existing Releases or assets are not overwritten.
- Chinese and English assets are reproducibly built; checksums, build witnesses, and GitHub provenance are retained with distinct purposes.
- The Codex CLI 0.153.2 compatibility boundary is unchanged; future, prerelease, and out-of-window versions remain excluded.

## Historical title backfill

Historical Release title backfill is an independent online metadata operation, outside the local build and Draft-only workflow. Releases v7.3.0, v7.4.0, v7.4.1, v7.4.2, and v7.4.3 were backfilled and read back individually; v7.2.0 and earlier were unchanged. All five before/after checks confirmed that `body_sha256`, assets, draft, prerelease, and published_at were unchanged. Per-release IDs, before/after titles, and preserved-field hashes are recorded in [`HISTORICAL_RELEASE_BACKFILL.json`](HISTORICAL_RELEASE_BACKFILL.json).

## Evidence status

Local package-only validation and logical-readonly independent review passed for V7.4.4. CI, the remote tag, Draft assets, and the public Release still require later online readback, and no real-account installation was run for this version. Historical title backfill is separately confirmed complete by online readback.
