# Release automation and artifact provenance

Chinese: [RELEASE_AUTOMATION.md](RELEASE_AUTOMATION.md)

## Objective

The release workflow treats source validation, reproducible building, provenance generation, and public Release publication as separate facts. Creating files is never reported as publication.

## Triggers and gates

- A manual `Release Candidate and Provenance` run builds and attests the current manifest version without creating a Release page.
- A pushed `vX.Y.Z` tag must exactly match both `manifest.json` and the Plugin manifest version or the workflow fails closed.
- Windows and Ubuntu run bilingual coverage, repository-wide link, and complete-package validation. Windows performs two byte-identical builds of each distribution.
- GitHub generates signed provenance for the Chinese and English ZIP files and preserves build witnesses, checksums, and the attestation bundle.
- A tag run can create only a **Draft Release**. An existing Release is not overwritten, and automation never publishes the draft.

## Verify downloaded artifacts

After downloading a ZIP, use GitHub CLI to verify the actual file digest and provenance against this repository identity:

```shell
gh attestation verify Codex-Skills-V7.2.0-zh-CN.zip --repo OWNER/REPOSITORY
gh attestation verify Codex-Skills-V7.2.0-en.zip --repo OWNER/REPOSITORY
```

Replace `OWNER/REPOSITORY` with the repository identity shown on the download page. `SHA256SUMS.txt` supports digest comparison, `witness-*.json` proves that two clean builds from the same commit were byte-identical, and the GitHub attestation binds ZIP digests to the workflow identity that produced them. These are distinct evidence layers and cannot substitute for one another.

## Publish a new version

1. Update manifests, the Plugin version, release notes, tests, and bilingual counterparts.
2. Complete CI and maintainer review on the branch.
3. Create and push a version tag that matches the manifest.
4. Wait for provenance generation and draft Release creation to succeed.
5. Manually inspect the version, both language ZIPs, witnesses, checksums, and provenance before deciding whether to publish the draft.

The workflow does not upload historical original ZIP files, replace existing assets automatically, or bypass maintainer publication approval.
