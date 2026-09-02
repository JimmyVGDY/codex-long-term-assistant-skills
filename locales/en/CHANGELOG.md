# Changelog

## 7.1.0 - 2026-09-02

### Changed

- Updated the current Codex CLI release baseline to 0.152.1, retained verified 0.150.1 compatibility, and kept fail-closed behavior for other versions.
- Synchronized current metadata, builds, release verification, documentation, and the 7.0.0 upgrade path to 7.1.0.

### Fixed

- Plugin and standalone modes transactionally install, verify, and remove the account-level `cp-runtime.py` and `evolution.py` launchers.
- Restricted tasks resolve the exact active Plugin-cache runtime from installation state.

## 7.0.0 - 2026-09-01

### Added

- Added language-neutral `backend-engineering` and independent `ai-engineering`.
- Added a four-domain responsibility matrix and 45 positive/negative routing cases covering Node.js, Go, .NET, Rust, mixed backends, pure AI, and AI plus GPU boundaries.
- Added bilingual documentation sites, repository-wide Markdown link auditing, versioned release evidence, reproducible bilingual artifacts, and draft-only GitHub Release automation with signed provenance.

### Changed

- Java and Python are progressive backend specializations; the data domain is now `data-middleware-infrastructure`.
- Manifest, AGENTS, bilingual documentation, recovery flows, and release tooling target 7.0.0.
- The bilingual landing page, navigation, and security support matrix now target V7. The project preview no longer embeds a release number and uses a reusable 1280×640 JPEG below GitHub's 1 MB upload limit.
- Main CI now reads versioned archive and witness names from constrained release metadata instead of hard-coding an older release.

### Fixed

- Fixed Material for MkDocs retaining stale repository release facts in browser session storage, which could leave `v6.6.1` in the header. The site now repairs both the cached and visible version facts.
- Upgrades remove only the four Manifest-declared legacy Skill directories while preserving unknown Skills and custom files.
- Fixed documentation language-selector paths and strict Pages inclusion for sibling English documents.

### Validation

- 128 package tests, 6 runtime tests, strict bilingual audit, Markdown link audit, and strict MkDocs build pass.
- The source tree completed a native Windows Codex CLI 0.150.1 `6.6.0 -> 7.0.0` Plugin upgrade readback, and a fresh read-only task selected the general backend and data-infrastructure routes. Public ZIP artifacts remain independently built and attested by the tag workflow.

## 6.6.1 - 2026-08-31

### Added

- Complete, independently installable, deterministic `zh-CN` and `en` archives.
- Human-reviewed English counterparts for every natural-language document, all ten Skills and their References and templates, seven Reviewer definitions, examples, structured descriptions, and Python runtime messages.
- Locale binding, reproducible-build checks, full-project translation coverage, and fail-closed runtime-literal validation.

### Fixed

- Bounded retry for transient Windows sharing failures during atomic file publication.
- Explicit validation-process waiting removes temporary-directory cleanup races while production SessionEnd remains asynchronously sealed outside the Hook budget.
- Windows batch launchers now use the UTF-8 code page and CRLF line endings. The neutral-language gate distinguishes the unshipped runtime source-string catalog from delivered prose.

### Security

- `execution_authorization=NONE`, dual project isolation, minimal metadata, and the Terra High automatic ceiling remain unchanged.
- Reviewer TOML files contain no hard-coded model. Diagnostic observations are not promoted to actual runtime model proof.
- Both archives exclude unrelated brands, personal paths, nested ZIPs, Git metadata, caches, and localization-source overlays.

Earlier reconstructed release history remains preserved by Git tags and archival records rather than being presented as newly translated evidence.
