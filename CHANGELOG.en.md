# Changelog — English current-release summary

中文完整历史：[`CHANGELOG.md`](CHANGELOG.md)

## 6.6.1 - 2026-08-31

### Added

- Complete, independently installable, deterministic `zh-CN` and `en` archives.
- English README, global rules, ten Skill entry points, seven Reviewer definitions, installation, configuration, operating, and release guidance.
- Locale binding, reproducible-build checks, and primary-surface language validation.

### Fixed

- Bounded retry for transient Windows sharing failures during atomic file publication.
- Explicit validation-process waiting removes temporary-directory cleanup races while production SessionEnd remains asynchronously sealed outside the Hook budget.

### Security

- `execution_authorization=NONE`, dual project isolation, minimal metadata, and the Terra High automatic ceiling remain unchanged.
- Reviewer TOML files contain no hard-coded model. Diagnostic observations are not promoted to actual runtime model proof.
- Both archives exclude unrelated brands, personal paths, nested ZIPs, Git metadata, caches, and localization-source overlays.

Earlier reconstructed release history remains preserved in the Chinese historical changelog and version tags rather than being presented as newly translated evidence.
