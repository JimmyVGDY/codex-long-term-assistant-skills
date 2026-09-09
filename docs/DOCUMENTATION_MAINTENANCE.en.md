<!-- Generated from locales/en/docs/DOCUMENTATION_MAINTENANCE.md; edit that source and run scripts/documentation.py sync. -->

# Documentation Maintenance and Fact Checks

This guide describes editing sources, check coverage, and release handoff. [documentation.json](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/config/documentation.json) owns document classification and language-source relationships.

Run the maintenance commands below from the root of a complete source checkout. A single-language release package excludes the `locales/en` and `.github` documentation sources. Packaged documents remain readable; editing bilingual sources or rebuilding the site requires the complete source.

## Editing sources

| Content | Maintained source | Generated or checked surfaces |
|---|---|---|
| Chinese guidance | Chinese sources in the root, docs and skills | Chinese site and release package |
| English guidance | Matching source under locales/en | Sibling *.en.md files, English site and package |
| Current package version | manifest.json; the plugin manifest must agree | Marked version projections |
| Hook registration | hooks/hooks.json | Marked names and counts; purpose still requires implementation review |
| Format versions | Templates, runtime constants and result schema | Manifest declarations and marked document tables |
| State ownership | authority_registry in manifest.json | Marked authority references |

English files marked `Generated from` are generated. Open the named source before editing; direct edits to a generated copy fail the consistency check.

## Routine changes

1. Read the relevant source, configuration, callers and current guidance. Distinguish package versions, protocol formats and historical introduction versions.
2. Edit both language sources. Register new docs files with their Chinese path, English source and status.
3. Run the following checks and add runtime validation when the changed behavior requires it.

```text
python scripts/documentation.py sync
python scripts/documentation.py check
python scripts/check-links.py --strict
python scripts/localization-audit.py --strict
python scripts/build-docs-site.py
```

Also run the existing documentation workflow's strict MkDocs build. A second `sync` must report an empty `updated` list; repeated generation must not hide changing source content.

## Current, reference and historical material

- `active`: current operations and constraints, included in default site search.
- `reference`: current on-demand material, included in default site search.
- `historical`: earlier release evidence, guides and designs, marked as historical and excluded from default search.
- `generated`: compatibility pages regenerated from canonical documents, excluded from default search. They retain existing section anchors.
- `english_projections` separately declares language projections. Generated copies have no independent fact ownership.

Before moving a file, check GitHub relative links, site URLs, key anchors, English projections and package references. Preserve compatibility pages or redirects for public entry points. Catalog `aliases` generates compatibility copies. Checks reject drift, cycles and multiple writers; site acceptance verifies old entry points and anchors.

Preserve historical version numbers rather than replacing old numbers globally. Where historical formats describe discontinued collection, add a historical notice and a link to the current protocol.

## Check coverage and limits

Automated checks cover catalog completeness, generated-copy drift, required fact markers, Hook counts and lists, known migration-boundary errors, current title versions, format declarations and budget ownership. They neither execute runtime code nor read project task state.

Natural-language applicability, authorization, safety limits and feature claims still require implementation review. A valid link does not prove correct guidance; a successful documentation build does not prove host loading, gate execution or business acceptance.

## Release evidence and maintenance cost

### Release source boundary

Local candidate builds read the current content of Git-tracked files. Stage new source, tests and English overlays first. Ignored files and unrelated untracked files never enter the snapshot. Staging is not a commit; a successful candidate build does not establish a published clean commit.

The formal release workflow captures a clean checkout once and builds both locales from that snapshot. To prepare a Gitless build, run this in a complete Git source checkout:

```text
python scripts/build-release.py snapshot --output <new-external-directory> --require-clean
```

Local candidates may omit `--require-clean`. A snapshot contains source, English inputs and `SOURCE_MANIFEST.json`, recording source HEAD, relative paths, sizes, SHA-256 values and a content digest. Enter the snapshot directory and use the existing `build` or `reproducible` command. Missing manifests or required inputs, content mismatches, path collisions and links fail the build. Unlisted extras cannot participate in English overlays. A manifest verifies content; a self-supplied manifest is not independent proof of trusted Git ancestry.

The source manifest is excluded from installation archives, payload and packaged checksums. A single-language installation archive is not a bilingual source snapshot. Capture limits are 10,000 files, 32 MiB per file and 256 MiB total. Exceeding a limit fails explicitly; inspect inputs before changing scope or implementation limits. Keep inputs stable during capture and retry the entire capture if source content or the Git file set changes.

Separate candidate validation from post-release readback. Completion statements must identify the version, full commit, verification time and exact workflow run, not only a mutable workflow listing. Read public status back; offline document checks cannot prove workflow success.

Packages retain evidence available at build time. Append later release, site and account-loading results to delivery records without rewriting published tags or artifacts. Earlier baseline results do not validate later edits.

Reuse existing checks and builders. Observe independent manual fact edits, check duration, scan volume and historical-cache storage. Split modules only with demonstrated benefit; do not add continuous scans, a second project index or duplicate state ledgers.

[Documentation hub](README.en.md) · [Authority registry](../locales/en/docs/AUTHORITY_REGISTRY.md) · [Release workflow](releases/RELEASE_AUTOMATION.en.md)

## Repository structure and entry points

| Location | Responsibility and stable entry |
|---|---|
| docs/USER_GUIDE.md | Current usage entry without a versioned filename |
| docs/operations/ | Configuration, installation and recovery |
| docs/architecture/ | Current architecture and boundaries |
| docs/history/ and docs/releases/ | Historical designs and version-bound release evidence |
| locales/en/ | English sources; other language surfaces are generated |
| hooks/ and runtime/ | Host adapters and shared runtime implementation |
| skills/, custom-agents/, global/ | Skill discovery, review roles and global rules |
| scripts/cp-runtime.py | Project binding, capability index and gate commands |
| scripts/package_manager.py | Install, verify and recover the plugin |
| scripts/validate-package.py | Complete package validation entry |
| tests/ and module-local tests/ | Cross-module regressions and domain tests |
| .agents/plugins/ and .codex-plugin/ | Fixed plugin discovery and package metadata |
| dist/ | Rebuildable outputs isolated by version and commit |

Task state, evidence archives and downloaded tools stay outside the repository. Preserve current Profile, index and gate bindings when archiving historical material. Archive files with hashes and a restoration map before removing originals.
