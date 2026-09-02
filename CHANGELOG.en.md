# Changelog — English current-release summary

Chinese full history: [`CHANGELOG.md`](CHANGELOG.md)

## Unreleased

None.

## 7.1.0 - 2026-09-02

### Changed

- Updated the current Codex CLI release baseline to 0.152.1, retained verified 0.150.1 compatibility, and kept fail-closed behavior for other versions.
- Synchronized Manifest, Plugin, bilingual builds, release verification, attestations, documentation site, and current operating guides to 7.1.0, with a declared 7.0.0 upgrade path.

### Fixed

- Plugin mode now transactionally installs and verifies the account-level `cp-runtime.py` and `evolution.py` launchers. When the account runtime is unreadable, both launchers resolve the exact active Plugin-cache version from installation state instead of reporting a missing `cp_runtime` module.
- Retained Marketplace/Plugin command and core `plugin list --json` contract checks on native Windows Codex CLI 0.152.1.
- Increased the complete-package command timeout from 300 to 600 seconds so slower GitHub Windows runners are not terminated before the test suite finishes.

## 7.0.0 - 2026-09-01

### Added

- Added language-neutral `backend-engineering` for Node.js, Go, .NET, Rust, Java, Python, and mixed-language services.
- Added independent `ai-engineering` for model integration, structured output, RAG, agents, evaluation, inference, GPU, and multimodal semantics.
- Added a four-domain responsibility matrix and 45 positive/negative routing cases.
- Rebuilt the documentation root as a bilingual project landing page with project identity, language cards, capability metrics, release and source links, responsive layouts, light and dark themes, and keyboard access.
- Added repository-wide Markdown path, anchor, and same-repository URL checks, with scheduled external-link probing.
- Added separate Chinese and English documentation sites published by GitHub Actions, with navigation, search, theme switching, and versioned release evidence.
- Added fail-closed tag-version validation, reproducible bilingual artifacts, GitHub-signed provenance, and draft-only Release automation.
- Added a bilingual GitHub Release page index for V1.0.0 through V6.6.0 and documented the zero-asset policy for historical original ZIP files.

### Changed

- Java and Python are now progressive backend specializations; the data domain is renamed to `data-middleware-infrastructure` and no longer owns AI product semantics.
- Manifest, AGENTS, bilingual documentation, recovery flows, release tooling, and package validation now target 7.0.0.
- The bilingual landing page, navigation, and security support matrix now target V7. The project preview no longer embeds a release number and uses a reusable 1280×640 JPEG below GitHub's 1 MB upload limit.
- Main CI now reads versioned archive and witness names from constrained release metadata instead of hard-coding an older release.

### Fixed

- Fixed Material for MkDocs retaining stale repository release facts in browser session storage, which could leave `v6.6.1` in the header. The site now repairs both the cached and visible version facts.
- Upgrades remove only the four Manifest-declared legacy Skill directories: three V7 domain replacements and the previously deprecated Vue Skill. Unknown Skills and custom files remain untouched.
- Worktree link auditing ignores tracked paths already removed from the working tree, allowing consistent validation during renames.
- Fixed the documentation language-selector path difference between repository checks and the generated Pages tree.
- Fixed strict Pages builds by copying newly added sibling English documents into the English site source tree.

### Validation

- 45 routing cases, 128 package tests, 6 runtime tests, strict bilingual audit, Markdown link audit, and strict MkDocs build pass.
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

Earlier reconstructed release history remains preserved in the Chinese historical changelog and version tags rather than being presented as newly translated evidence.
