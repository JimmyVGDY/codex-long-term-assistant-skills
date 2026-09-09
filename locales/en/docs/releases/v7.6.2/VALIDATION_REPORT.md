# V7.6.2 Validation Record

Validation date: 2026-09-09. The facts below describe implementation and validation completed for the final local candidate.

| Area | Current result and boundary |
|---|---|
| Hook registration | Native asynchronous UserPromptSubmit registration is covered. Each of the 11 frozen versions binds an official tag, commit, source path, and SHA-256. The online verifier resolved each official tag, read commit-pinned source, and checked its digest and three semantic markers; 11/11 passed. |
| Legacy-gate isolation | UserPromptSubmit/Stop do not read or mutate legacy task state; native writes fail closed when the legacy policy is enabled and the legacy origin is unavailable; unconfigured or disabled policies remain neutral. |
| Focused tests | 40 installer tests, 16 evolution-feedback tests, 11 runtime Hook tests, and 18 compatibility/async-registration tests passed. |
| Full candidate validation | `validate-v74.py` passed: 325 package tests and 143 runtime tests, plus semantic, privacy, payload, dispatch-policy, routing-case, and worktree-side-effect checks. Machine report SHA-256: `f75d0ded1012ff7cd91c2538cc4f46f833b55150b8c24fb5028754a3284fb1aa`. |
| Independent review | Logical-readonly state/concurrency review passed. Compatibility review had no blocker; its release-evidence recording note is addressed in this final record. No system-readonly isolation is claimed. |
| Out of scope | Local package validation does not prove public publication, account installation, restart, fresh-task loading, or the cross-platform real-host matrix; each requires separate readback. |

Commit, push, publication, installation, restart, and effective state still require separate post-action readback.
