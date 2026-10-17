<!-- Generated from locales/en/docs/releases/v7.17.1/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.17.1 Audit Record

The audit scope is the closed compatibility window, official-source binding, departing versions, release material, and delivery gates for Codex Desktop internal component 0.163.0. It does not establish standalone CLI product support or change the six Skill behaviors published in V7.17.0.

## Confirmed design

- The four critical official-source digests for 0.163.0 match 0.162.x. Reusing `result-v162` is more consistent with fail-closed behavior than inventing an unsupported profile.
- The window remains the anchor plus ten preceding stable releases; 0.157.0 leaves the window, while unknown and prerelease versions continue to fail closed.
- Management CLI, account Plugin, actual bundled Desktop component, package validation, Git, CI, tag, Release, and public downloads remain distinct evidence layers.
- `config/published-release.json` continues to record the published V7.17.0 fact until the new version is public; it does not predeclare V7.17.1 publication.

## Review status

The pre-implementation Reviewer could not be dispatched because the original root had exhausted its allowance and native TaskScope origin was unavailable at that time. This gap limits review claims but did not block isolated, reversible local evidence freezing. Before publication, independent compatibility and delivery review must run against the final diff and current validation packet; any later repair invalidates affected tests and review conclusions.

No upstream protocol drift requiring changes to V7.17.0 runtime behavior has been found. Unfinished validation, installation, or release actions remain unverified and are not promoted to PASS by this report.

## Post-implementation independent review

- The first logical-readonly review returned one blocking finding: the bilingual `release_name` and Plugin descriptions still used the V7.17.0 theme. It also recorded unclear target-commit metadata in the review packet.
- After repair, the public title reads `V7.17.1 | Codex 0.163.0 内部组件兼容 / Codex 0.163.0 internal component compatibility`; the bilingual Plugin descriptions agree, and the 350-file payload digest is `56b99b738c55c77b5d0fd7465c622b64e1f6c6330b11912b095144a5e20879e7`.
- The refreshed packet binds commit `d9ef9af06d0ba4de75fa774e01e4eba817cccb9d` and has SHA-256 `67944f091220f1324e222b92c38bb434b968e60bf8e409d0d722adb7ec637229`. The second targeted review concluded `pass` with no remaining findings.
- The reviewer did not run tests, install, commit, push, tag, or publish. Remote CI, account Plugin, actual Desktop, Release, and public assets remain later independent gates.
