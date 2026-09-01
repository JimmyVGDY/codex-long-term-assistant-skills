# Changelog — English current-release summary

Chinese full history: [`CHANGELOG.md`](CHANGELOG.md)

## Unreleased

- Add repository-wide Markdown path, anchor, and same-repository URL checks, with scheduled external-link probing.
- Add separate Chinese and English documentation sites published by GitHub Actions, with navigation, search, theme switching, and versioned release evidence.
- Fix the documentation language selector path difference between repository checks and the generated Pages tree.
- Add fail-closed tag-version validation, reproducible bilingual artifacts, GitHub-signed provenance, and draft-only Release automation.
- Add a bilingual GitHub Release page index for V1.0.0 through V6.6.0 and document the zero-asset policy that keeps historical original ZIP files private.
- Fix strict Pages builds by copying newly added sibling English documents into the English site source tree.

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
