# Changelog — English current-release summary

Chinese full history: [`CHANGELOG.md`](CHANGELOG.md)

## Unreleased

None.

## 7.4.3 - 2026-09-04

### Changed

- Model governance now uses only the pre-dispatch approved profile, permit reference, reserved units, and outcome attribution. Host runtime model identity and reasoning effort are no longer read, inferred, stored, attested, billed, or used by release gates.
- TaskOutcomeEvent advances to V3, DelegationBudget to V2, and Reviewer results to V4. Calibration and Evolution now compare outcome value per reserved unit between approved profiles.

### Fixed

- Legacy Event V2 and Budget V1 chains are verified against their original contracts before recursive safe projection. Legacy and current schemas use separate chains and cannot be mixed.
- Reviewer state migration no longer reserializes historical runtime model fields, and release tooling adds privacy-boundary and abstract dispatch-policy gates.
- Account reinstall no longer copies Python bytecode; Hooks, the worker, and account tools no longer mutate the managed Plugin cache; SessionEnd signed-job creation, scanning, and movement support Windows long paths; and the Windows Hook is normalized to CRLF so checkout conversion cannot change the payload digest.

### Validation

- V7.4.3 reports local unit, bilingual, privacy, lifecycle, compatibility-chain, reproducible-build, independent-review, and Windows account-reinstall evidence separately. Remote CI, push, tag, and public Release still require explicit readback.

## 7.4.2 - 2026-09-04

### Changed

- Advanced the closed registry anchor to Codex CLI 0.153.2 and updated the eleven-stable-release window to 0.153.2 through 0.148.0.
- Updated Plugin metadata, installer, bilingual builds, validators, documentation site, and the Windows/Ubuntu compatibility matrix while preserving V7.4.1 historical evidence.

### Fixed

- Pinned official 0.153.1/0.153.2 artifacts and normalized CLI/Plugin digests while retaining fail-closed behavior for future, prerelease, and exited versions.
- Added regressions preventing stale untrusted runtime evidence after a model switch and preventing `unified_exec` from consuming sub-agent dispatch permits or budget.

### Validation

- Windows isolated CLI, Plugin round-trip, synthetic Hook, and artifact checks pass for 0.153.1/0.153.2. Full-window, real-account, CI, review, and public-release evidence is reported separately in the V7.4.2 reports.

## 7.4.1 - 2026-09-03

### Added

- Added a closed Codex compatibility registry for 0.153.0 and the ten preceding stable releases, binding official npm artifacts, capability profiles, and layered evidence states.
- Added a 22-cell Windows/Ubuntu release matrix, isolated `CODEX_HOME` Plugin preflight, and schema-3 CLI/registry/capability/payload host snapshots.

### Changed

- Expanded Plugin mode from only 0.153.0 to eleven pinned stable releases while keeping future, prerelease, and out-of-window versions fail-closed.
- Reduced Marketplace ownership to managed fields while preserving unknown top-level data, nested `interface` data, `owner`, and other Plugin entries.
- Registered Hook snake_case, camelCase, and compatibility aliases consistently. Security conflicts deny dispatch, observation conflicts remain unavailable, and Stop/SubagentStop return neutral JSON.

### Fixed

- `verify`, `status`, and `doctor` now detect CLI file, registry, profile, and capability drift instead of comparing version alone.
- The Windows matrix can bind an explicit Codex executable so PATH resolution cannot select the global version accidentally.
- Release builds and runtime-text audits exclude repository-external `project-context` evidence so temporary official CLIs cannot enter an archive.

### Validation

- All eleven official Windows CLIs passed CLI, isolated Plugin, and synthetic Hook cells under registry digest `1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8`. GitHub Ubuntu, real-account, and public-release states remain separate evidence.

## 7.4.0 - 2026-09-03

### Added

- Added repository-external DelegationBudget V1, one append-only hashed root-task budget for Reviewer, Explorer, and Worker.
- Added controlled route reasons, explicit dispatch permits, idempotent reservations, trusted actual-profile top-ups, host-proven not-started release, and budget closure.
- Added role-specific scenario calibration and adjacent-tier offline replay. Only the parent coordinator can finalize samples, and proposals retain `execution_authorization=NONE`.

### Changed

- Upgraded Task Envelope to schema 3, execution state to schema 4, and review state to schema 6 while keeping V7.3 state readable.
- The Reviewer controller now owns rounds and findings only; DelegationBudget exclusively owns total charging.
- Updated the Plugin target to Codex CLI 0.153.0 and generate its required Marketplace `interface.displayName`. The ten-preceding-stable compatibility window is deferred to V7.4.1.

### Fixed

- PreToolUse fails closed on missing stable dispatch identity, unknown roles, permit mismatch, exhaustion, or chain corruption, while Hook replay remains idempotent.
- Start/Stop without a reservation correlation remains unavailable instead of being guessed; ordinary Hook model fields are never reported as trusted runtime evidence.
- Started agents are never refunded. Only explicit host proof of not starting releases a reservation.

### Validation

- Added regressions for unified accounting, concurrency, nesting, Hook permits, single-owner Reviewer charging, privacy, tamper detection, parent finalization, and insufficient-data no-change behavior. Full package, real 0.153.0 installation, independent review, and public artifact evidence are reported separately.

## 7.3.0 - 2026-09-02

### Added

- Added `minimum_acceptable_profile` to Reviewer dispatch and an append-only `INLINE/DELEGATE` decision gate; `INLINE` creates no round and consumes no Reviewer budget.
- Added Reviewer result schema v3 with task difficulty, duration, pending attribution, finding disposition, and `profile-weight-v1` estimated cost, projected by the controller into a deduplicated calibration ledger; Reviewers cannot finalize attribution themselves.

### Changed

- Reviewer declarations now produce only `declared_match/fallback_acceptable/underpowered/unverified/mismatch`. Results below the minimum acceptable tier may only be `incomplete` and cannot be merged or closed normally.
- Evolution keeps missing cost unknown, segments metrics by Reviewer, model tier, and task difficulty, and excludes unfinalized attribution from low-yield classification; default routing stays unchanged when real evidence is insufficient.
- Aligned the bilingual site's current V7.3 system architecture, domain routing, configuration, controlled-evolution, and authoritative-source documentation. Earlier versions now appear only for migration or historical evidence.
- Added prominent bilingual notices to historical detail pages during site generation and excluded those pages from default site search while keeping current and release-archive indexes searchable.

### Fixed

- Fixed Plugin-mode launchers selecting a stale standalone runtime ahead of the installed versioned cache; Plugin mode now uses only its state-bound cache and fails closed when that cache is missing.
- Removed historical-version labels mixed into current navigation and specifications, and replaced a dead command that referenced a removed validator.
- Reconciled the previously divergent Chinese and English Codex configuration guides and added regression gates for the current-document inventory, historical isolation, and referenced public scripts.
- Fixed self-referential Chinese links on current English pages, Unicode heading anchors, and a stale table label; version changes now trigger Pages and fail closed when site entry points drift from the manifest.

### Validation

- Added regressions for minimum tiers, INLINE redecision, legacy v2 result compatibility, calibration projection, unknown cost, and unfinalized attribution. Local installation and real-data readback are reported separately at task delivery.

## 7.2.0 - 2026-09-02

### Added

- Added eleven real Codex host-routing acceptance scenarios, schema-2 observations, and SHA-256-bound final-report evidence.
- Added a persisted controlled-evolution end-to-end case from observation, snapshot, and assessment to an `execution_authorization=NONE` proposal registry.

### Changed

- Set Python 3.11 as the minimum and cover both 3.11 and 3.13 on Windows and Ubuntu CI.
- Evaluate controlled-evolution evidence per signal and calculate coverage over unique `task_id` values; model escalation and negative outcomes consume only their required evidence.
- Removed duplicated controlled-evolution guidance from `long-running-task-memory` and `multi-agent-independent-review`, routing both to `controlled-evolution-governance`.

### Fixed

- Complete validation now binds the Git index, tracked and untracked content digests, deletions, and link states, runs the post-snapshot even after interrupts, and refuses repository-local output.
- Host-routing acceptance rejects unknown Skills, duplicate tasks or reports, non-finite pass rates, hash/byte-count mismatches, and report-field drift while separating host final reports from internal router traces.
- The installer removes local Marketplace top-level `owner/interface` fields rejected by Codex CLI 0.152.1 while preserving unknown external metadata.

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
