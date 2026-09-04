# Release automation and artifact provenance

Chinese: [RELEASE_AUTOMATION.md](RELEASE_AUTOMATION.md)

## Objective

The release workflow treats source validation, reproducible building, provenance generation, and public Release publication as separate facts. Creating files is never reported as publication.

## Title source and constraints

- The Chinese title comes from `manifest.json.release_name`; the English title comes from `locales/en/manifest-localization.json.release_name`.
- Titles must be non-empty strings. Whitespace-only values, leading or trailing spaces, control or format characters, overlong values, and generic placeholders fail closed.
- Length limits are 30 code points for Chinese, 80 for English, and 125 code points or 200 UTF-8 bytes for the combined title; Unicode `Cc`, `Cf`, and `Cs` categories are rejected.
- The workflow writes the title to a job output and passes it through an environment variable, avoiding direct shell-expression interpolation.
- The tag flow is Draft-only; an existing Release is not overwritten, and assets, checksums, witnesses, and provenance remain separately verifiable.

## Triggers and gates

- A manual `Release Candidate and Provenance` run builds and attests the current manifest version without creating a Release page.
- A pushed `vX.Y.Z` tag must exactly match both `manifest.json` and the Plugin manifest version or the workflow fails closed.
- Windows and Ubuntu run bilingual coverage, repository-wide link, and complete-package validation. Windows performs two byte-identical builds of each distribution.
- GitHub generates signed provenance for the Chinese and English ZIP files and preserves build witnesses, checksums, and the attestation bundle.
- A tag run can create only a **Draft Release**. An existing Release is not overwritten, and automation never publishes the draft.

## Verify downloaded artifacts

After downloading a ZIP, use GitHub CLI to verify the actual file digest and provenance against this repository identity:

```shell
gh attestation verify Codex-Skills-V7.4.5-zh-CN.zip --repo OWNER/REPOSITORY
gh attestation verify Codex-Skills-V7.4.5-en.zip --repo OWNER/REPOSITORY
```

Replace `OWNER/REPOSITORY` with the repository identity shown on the download page. `SHA256SUMS.txt` supports digest comparison, `witness-*.json` proves that two clean builds from the same commit were byte-identical, and the GitHub attestation binds ZIP digests to the workflow identity that produced them. These are distinct evidence layers and cannot substitute for one another.

V7.4.5 English title segment: `Codex CLI 0.153.3 stable compatibility`; the complete bilingual title is assembled from the two manifest values.

## Publish a new version

1. Update manifests, the Plugin version, release notes, tests, and bilingual counterparts.
2. Complete CI and maintainer review on the branch.
3. Create and push a version tag that matches the manifest.
4. Wait for provenance generation and draft Release creation to succeed.
5. Manually inspect the version, both language ZIPs, witnesses, checksums, and provenance before deciding whether to publish the draft.

## Failure handling and rollback boundaries

- **CI fails before a Draft exists:** keep the Release absent and diagnose the failed gate. If source changes are required, use a new commit and patch version; do not blindly rerun or automatically move the remote tag.
- **A Draft has an incorrect title, body, or asset:** keep it unpublished and do not use `--clobber`. Correct only auditable metadata. If assets or the source commit are wrong, stop and require explicit maintainer approval to delete the draft or issue a new patch version.
- **A tag points to the wrong commit:** automation must not force-push, delete, or recreate it. If no Release exists, a maintainer may separately authorize correction after checking protection rules and impact; the default is a new version. Never retarget a tag associated with a public Release.
- **A public Release is found to be wrong:** do not automatically withdraw it or silently replace binaries. Prefer a corrective release and an amendment notice on the original; metadata edits, withdrawal, or deletion require separate authorization and before/after readback.

Failure handling must continue to distinguish commit, push, tag, CI, Draft, public Release, and effective installation. A failure at one stage cannot be reported as completion of any later stage.

Historical Release title backfill is an independent online metadata operation and is not performed by the Draft-only flow. Releases v7.3.0 through v7.4.3 were completed and read back individually; v7.2.0 and earlier were unchanged.

The workflow does not upload historical original ZIP files, replace existing assets automatically, or bypass maintainer publication approval.

The checklist must also confirm title sources and constraints, job-output/environment-variable transport, Draft-only behavior, existing-Release no-overwrite behavior, bilingual assets and provenance, the Codex CLI 0.153.3 compatibility boundary, and independent authorization/readback for historical title backfill.
