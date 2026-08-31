# V6.6 Release Notes

Version: 6.6.0
Target host: Native Windows Codex CLI 0.150.1

## Additions

1. Added a contract for trusted host evidence of the actual runtime model. Evidence must bind the issuer, attestation ID, validity period, Hook, session, turn, agent, model, and reasoning effort, and must validate against an external trust anchor.
2. Added Windows fault tests for true spawned processes, forced termination, PID reuse, and interrupted atomic replacement of the keyring and seals.
3. Added a signed SessionEnd queue and detached worker. SessionEnd does not scan or seal the full chain; enqueue or launch failure produces an explicit diagnostic without recording source text.
4. Reviewer calibration now includes task-difficulty distribution, repeated root-cause clusters, adoption reasons, and regression-prevention benefits backed by regression evidence.
5. Added non-destructive event archival, capacity budgets, and privacy-constrained cross-project health summaries. Reparse-point escapes fail closed, while corruption in one project is isolated.
6. Fixed three distinct model-evidence fields:

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

## Compatibility

- TaskOutcomeEvent remains at schema 2.0; historical V6.0-V6.5 records are not rewritten.
- The V6.5 keyring remains compatible in place. RETIRED keys are retained and continue to verify historical seals and attestations.
- The 10 Skills, 7 Reviewers, 6 Hooks, and Terra High automatic ceiling are unchanged.
- The main Agent model configuration is not rewritten, and Reviewer TOML files do not hard-code models.
- `execution_authorization=NONE`, human Proposal decisions, and the boundaries against automatic commit, push, and deployment remain unchanged.

## Current Host Limitation

Codex 0.150.1 does not provide Hooks with actual-model evidence that can be verified against an external trust anchor. Requested-model policy and lifecycle validation can therefore pass, but the actual runtime model must remain `UNAVAILABLE`; model and reasoning-effort observations from the rollout remain `DIAGNOSTIC` only.
