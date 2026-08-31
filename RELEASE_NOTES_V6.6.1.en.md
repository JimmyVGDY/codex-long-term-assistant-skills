# V6.6.1 Release Notes

中文：[`RELEASE_NOTES_V6.6.1.md`](RELEASE_NOTES_V6.6.1.md)

## Delivered

- Two reproducible, independent archives: `zh-CN` and `en`.
- English primary surfaces for README, global rules, ten Skill entry points, seven Reviewer definitions, installation, configuration, operating guidance, and release notes.
- Bounded retry for transient Windows atomic-publication sharing failures.
- Explicit validation-only worker waiting, while production SessionEnd remains detached and bounded by the three-second host timeout.
- Exact Plugin acceptance remains `installed=true`, `enabled=true`, and `version=6.6.1`.

## Unchanged safety policy

- `execution_authorization=NONE`
- no automatic Skill or Reviewer modification
- no automatic proposal acceptance or execution
- no automatic commit, push, deployment, restart, production operation, or data write
- no hard-coded Reviewer model
- automatic model ceiling remains `gpt-5.6-terra + high`

## Runtime evidence statement

Codex 0.150.1 still supplies diagnostic observations rather than trusted runtime model attestation:

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = diagnostic only
```
