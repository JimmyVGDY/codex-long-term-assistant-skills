<!-- Generated from locales/en/docs/releases/v7.17.1/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.17.1 Release Notes

V7.17.1 is a Codex Desktop internal-component compatibility patch based on the published V7.17.0 release. It advances the frozen window to official stable 0.163.0 and the ten preceding stable releases, removing 0.157.0 from the tail. The product scope remains Codex Desktop only; this release does not establish a standalone CLI support track.

- Official tag `rust-v0.163.0` resolves to commit `83086188ae0614bd882818ff1aa23f3194962012`.
- npm integrity is `sha512-HNd7vR9oTK6M2ikxFnvNDCdYUgAsyo9VVnd5KnEd2ON0GYI++7MiX9XNPUkhtdgGKFPsWS+CEppQ1UU63uVhUw==`; the tarball SHA-256 is `1a71db36560bb446d2c2e63ae675c4a3018c38ace38ca533f8d1b25d3e6555b4`.
- The 0.163.0 Hook discovery, Hook schema, apply_patch handler, and context digests are unchanged from 0.162.x, so the frozen `result-v162` profile is reused without inventing a new protocol branch.
- The isolated Windows version, Plugin JSON, Marketplace/Plugin help commands, Plugin preflight, and synthetic Hook contracts were replayed against 0.163.0.
- Upstream `/config`, immediate steering and interruption, leader-key, background-server restart, parallel read-only tools, permission restoration, and network-proxy changes do not automatically alter this package's reviewer, budget, TaskScope, or Operation v2 contracts.

The six Skill-quality workflows, task allowances, and gate-recovery implementation delivered in V7.17.0 remain unchanged. Full package, runtime, documentation, reproducible-build, independent-review, account Plugin, and actual Desktop-process acceptance must still pass on the final release commit; this document does not turn unfinished steps into PASS.
