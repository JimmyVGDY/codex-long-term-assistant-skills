# V6.5 Audit Report

Status: in-package static and automated audits are complete. Official host state is governed by the external upgrade report and attestation.

## Audit Conclusions

- Host JSONL is restricted to diagnostic evidence and cannot independently satisfy a model-compliance conclusion.
- Unified release verification and attestation validate the installed PreToolUse model-gate report. Real lifecycle and model-policy evidence remain separate; missing actual-model fields from the host do not weaken the trust classification.
- Event integrity uses detached seals, avoiding an unverifiable chain when V6.4 and V6.5 processes write concurrently.
- Windows DPAPI and POSIX mode-0600 boundaries are explicit. Backend, binding, or issuer mismatch fails closed.
- The keyring exposes no secret-export, deletion, or automatic-cleanup capability.
- Reviewer results without stable identity are excluded from calibration. Replays are deduplicated and identity conflicts enter `CONFLICT`.
- TaskOutcomeEvent 2.0, dual project isolation, the model gate, and controlled-evolution authorization remain compatible.
- No main-Agent model write or hard-coded Reviewer TOML model was found.

## Independent Review

Pre-implementation security and compatibility reviews identified five blockers and one non-blocking compatibility issue. Every item was incorporated into the revised design and test matrix. Post-implementation review is recorded separately in the official delivery report.
