# V7.4.3 Validation Report

Status: local release-candidate validation and Windows account-level reinstallation passed. Remote CI, tag creation, and public Release publication have not run.

## Validated scope

- Runtime events, budget, Reviewer, calibration, Evolution, and release reports use approved dispatch profiles and reserved units without depending on host runtime model identity.
- Event V3 is separate from Event V2, and Budget V2 is separate from Budget V1. Legacy chains are exposed only through a safe projection after read-only verification.
- Lifecycle Acceptance V2 checks event order, correlation, project isolation, chain and seal status, plus the absence of host model identity in its output.
- Dispatch-policy acceptance covers allowed profiles, the Terra High automatic ceiling, and fail-closed rejection above the ceiling while emitting only abstract policy conclusions.
- Privacy-boundary lint covers active code, configuration, current documentation, and release scripts.
- Package gates passed 233 repository tests and 6 runtime tests; strict localization, semantic checks, and payload integrity passed.
- A Windows account completed a transactional V7.4.2-to-V7.4.3 reinstall on Codex CLI 0.153.2. Plugin readback reports installed/enabled, with ten Skills, seven Reviewers, six Hooks, and no live transaction.
- The source, account Marketplace, and versioned cache each contain 182 managed payload files with the same digest: `48cda73843f7b7feb7093f752374291630a2431b66f97aef699e64ae377f9904`.
- The installed `cp_hook.cmd` completed a five-event parent/child lifecycle. SessionEnd reached `SEALED_CURRENT` over all five records, and the report read or exported no host model information, raw session/task IDs, prompts, or responses.
- Account validation found and repaired stale Python-bytecode copying and a Windows long-path signed-job failure. After the final reinstall and Hook run, neither the Marketplace nor the cache contained `.pyc` files.
- Account uninstall dry-run passed managed-hash and backup-manifest checks; no real uninstall or rollback was performed.
- Internal link audit covered 514 Markdown files and 572 links with zero findings and zero warnings.
- Both locale candidate ZIPs produced identical digests across two builds and passed normalized-metadata and embedded-version verification.
- Blocking root causes from post-implementation review were repaired and closed by the original finding owners; the final conclusion is logically read-only review complete with no blocking findings.

## Pending final readback

- Complete Windows/Ubuntu CI and the pinned Codex compatibility matrix;
- real account-level uninstall/rollback and Release Attestation; isolated install/rollback is covered by automated tests;
- `origin/main`, the `v7.4.3` tag, and the public Release.

No pending item inherits a pass from V7.4.2 historical evidence.
