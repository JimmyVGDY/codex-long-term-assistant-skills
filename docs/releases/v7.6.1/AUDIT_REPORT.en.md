<!-- Generated from locales/en/docs/releases/v7.6.1/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.6.1 Audit Record

Scope: current documentation facts, English sources, compatible directory migration and release source capture. Findings use current code, configuration and local verification. The global core-rule revision, package version and data-format versions remain distinct.

Independent postimplementation review found two nonblocking issues in source capture: Git output limits applied after capture, and malformed manifest structures without explicit validation. Both were repaired using bounded streaming reads and structural checks, with focused tests. A second review of that scope passed without new findings. The Reviewer was logically read-only. Later documentation facts and fixture isolation changes received focused validation; this does not claim that the same review covered the entire final worktree.

The documentation catalog manages active, reference, historical and generated content; locales/en is the English authority. The first migration preserves old entry points and sections without moving runtime, public CLI or Skill paths. A source snapshot manifest proves listed content hashes, not trusted publisher identity by itself. Formal releases additionally require a clean commit, CI and provenance.

Index candidates provide location evidence only; a gate PASS does not approve semantic reuse. Unverified hosts and platforms are not marked passed. The first complete-package command's two failures, repairs and reruns remain in the [validation record](VALIDATION_REPORT.en.md).
