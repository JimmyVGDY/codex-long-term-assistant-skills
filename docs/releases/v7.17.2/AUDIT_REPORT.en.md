<!-- Generated from locales/en/docs/releases/v7.17.2/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.17.2 Audit Report

The [V7.17.2 release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.17.2) became public at 2026-10-21 15:05:43 UTC. It is neither a draft nor a prerelease. All six assets were downloaded anonymously and checked against their verified digests, reproducible-build witnesses and GitHub provenance.

Independent security and state/concurrency static reviews passed. Native host proof, file replacement and missing-cache retry defects from the first round were repaired together; the second round found no actionable in-scope issues. Reviews were logically read-only, without a system-isolation claim. The review packet digest is `7be4177f621059736b62db4620425bc5685d5941ba9a355aa967c3e135e7a243`. Implementation and tests remained unchanged afterward; only reports were updated. The PR-tested and final tagged commits share Git tree `2d34a6b922309e767c123e007349ee0f4632d2bb`.

Recovery requires a native parent Hook locator; a caller path only cross-checks it. It stores no prompt bodies and changes no budgets, authorization or conflicting sources. The current Desktop session read back a genuine host locator, and all 350 installed payload files match the release. This does not prove host-enforced budgets or system isolation. Account signing keys are not rotated automatically.

Full master CI completed successfully for the tagged commit. Release validation, build, attestation and draft steps have successful evidence. An initial failure in an unchanged test and one successful same-source retry are retained. At public verification, one GitHub check summary still showed `in_progress` despite successful steps and test logs; no check status was rewritten and no gate disabled. See the [validation report](VALIDATION_REPORT.en.md).
