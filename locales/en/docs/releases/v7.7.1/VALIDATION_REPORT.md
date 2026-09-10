# V7.7.1 Validation Report

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/v7.7.1/VALIDATION_REPORT/)

- Official gate: GitHub stable Release and npm `latest` both report 0.154.0, published at 2026-09-09T22:35:38Z and 2026-09-09T22:40:10.746Z respectively.
- Active Windows CLI: the same global npm path was updated from 0.153.4 to 0.154.0; a fresh process passed version, help, login-status, and Plugin-list readback.
- Compatibility registry: eleven stable releases anchored at 0.154.0 with a 0.150.0 lower bound; 0.149.1, future, prerelease, and other out-of-window versions fail closed.
- Official sources: online digest verification passes 11/11 Hook async, PreToolUse/PostToolUse schema, and successful `apply_patch` result sources.
- Isolated 0.154.0 cell: official npm SRI/SHA-256, CLI contract, isolated Plugin round trip, and synthetic Hook pass.
- Focused unit tests: 19 compatibility-registry and async-Hook-registration tests pass.
- Full local package validation: the repaired final baseline passes 329 package and 180 runtime regressions on Python 3.13.15, together with semantic, privacy, routing, payload, and worktree-side-effect gates. An earlier run hit a Windows temporary-keyring concurrent-read `PermissionError`; the case and a later full rerun passed. The first registry-digest integration run exposed two legacy attestation fixtures; both focused tests and the final full wrapper passed after those fixtures were updated.

Independent postimplementation review, account-level transactional installation, fresh-task loading, remote CI, tag, six Release assets, and anonymous download readback are recorded separately at their respective stages. This report does not infer completion before direct evidence exists.
