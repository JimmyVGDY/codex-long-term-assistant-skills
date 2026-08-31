## Purpose

<!-- Describe the target problem, scope, and explicit non-goals. -->

## Main changes

- Add a concise item.

## Validation evidence

| Check | Actual result |
| --- | --- |
| Bilingual coverage audit |  |
| Package validation |  |
| Other focused validation |  |

## Compatibility, risk, and rollback

<!-- Describe compatibility impact, unverified items, remaining risk, and rollback path. -->

## Checklist

- [ ] The change is minimal and sufficient, without unrelated refactoring.
- [ ] Chinese and English documents and runtime language are synchronized.
- [ ] No credentials, private paths, or sensitive content were added.
- [ ] Reviewer definitions do not hard-code a model or reasoning effort.
- [ ] Automatic dispatch stays within Terra High and controlled evolution remains at `execution_authorization=NONE`.
- [ ] Commit messages follow `<type> | <Chinese summary>`.
