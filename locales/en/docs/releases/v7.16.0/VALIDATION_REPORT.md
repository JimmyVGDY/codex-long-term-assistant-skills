# V7.16.0 validation report

The stable release was published on **2026-10-12 at 01:46:47 UTC (09:46:47 Asia/Shanghai)**. These results apply to commit `3b1c1043172062c19a7e1c6da5e5240e86063447`; subsequent documentation corrections do not rewrite that tag or its signed assets.

## CI and artifacts

The [release workflow](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38037348930) passed all four complete validation jobs, bilingual reproducible builds, signed provenance generation, and draft creation.

| Platform | Python | Package tests | Runtime tests |
|---|---|---|---|
| Ubuntu | 3.11 | 1,133 passed; 42 conditional skips | 233 passed; 6 conditional skips |
| Ubuntu | 3.13 | 1,133 passed; 42 conditional skips | 233 passed; 6 conditional skips |
| Windows | 3.11 | 1,173 passed; 2 conditional skips | 239 passed |
| Windows | 3.13 | 1,174 passed; 1 conditional skip | 239 passed |

[Master CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38037349305) passed on its second attempt. One Node subprocess timed out on Windows/Python 3.13 in the first attempt. That failure remains recorded; no assertion was weakened and the test was not skipped or removed to obtain success.

Both ZIP SHA-256 digests, two-build witnesses, and GitHub provenance signatures were verified against this repository, `refs/tags/v7.16.0`, the source commit above, the release workflow, and hosted runners. All six public assets were downloaded anonymously on 2026-10-12; their sizes and digests matched the signed candidate. Downloads and verification files are on the [public Release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.16.0).

## Actual entrypoints and local readback

- The installed inventory covers 8 Hook event types, 12 managed registrations, and 9 script entrypoints.
- An in-repository absolute-path patch completed through the real Desktop write path with the gate enabled. Its operation receipt is `VERIFIED`; partial index coverage remains `UNVERIFIED`.
- Native agent continuation reserves a new attempt in the original root. Earlier-turn receipts cannot settle the new turn. Actual fees were unavailable; planning units are not reported as credits.
- A 2,045,074-byte native transcript was reconciled using the original handle. Its outcome remains `UNKNOWN`, completed calls no longer occupy concurrency, and replay does not charge twice.
- Managed reinstallation on 2026-10-12 refreshed the changed Desktop management-component binding. Installation verification passed, 329 payload files matched the official Chinese package, and historical ledgers were unchanged.
- The [bilingual documentation deployment](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38037349322) passed and both public pages were read back at publication. Later documentation changes have their own deployment evidence.

## Review and retained limits

Independent logical-readonly review and fix verification completed; see the [audit report](AUDIT_REPORT.md). Logical-readonly does not establish system isolation, and package tests do not validate every Desktop environment.

One probe-file cleanup lacked a host receipt. The file is absent, but the operation remains `OUTCOME_UNKNOWN`; no successful receipt was fabricated. Index coverage remains `UNVERIFIED`. Unknown fees, frozen policies, and historical failure records remain intact.

Negative cases retain restrictions for path escapes, sensitive paths, identity conflicts, damaged ledgers, and real budget exhaustion. macOS and untested host combinations have no acceptance claim. Desktop was not restarted and no restart is claimed.
