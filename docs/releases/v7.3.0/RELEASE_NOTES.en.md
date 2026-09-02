# V7.3.0 Release Notes

Chinese: [RELEASE_NOTES.md](RELEASE_NOTES.md)

Version: 7.3.0

## Key changes

- Reviewer dispatch now carries `minimum_acceptable_profile`. A result below that minimum may only remain `incomplete`; it cannot be merged or closed normally.
- An append-only `INLINE/DELEGATE` gate avoids creating a Reviewer round or consuming Reviewer budget for inline handling, while later redecisions preserve the full trail as new records.
- Reviewer results move to schema v3 with task difficulty, duration, pending attribution, finding disposition, and `profile-weight-v1` estimated cost. Only the controller may finalize attribution from merge outcomes.
- Controlled evolution segments cost and yield by Reviewer, model profile, and task difficulty. Missing cost remains unknown, unfinalized attribution is excluded from low-yield decisions, and default routing stays unchanged when real evidence is insufficient.
- Plugin launchers now load only the versioned cache bound to installation state. A stale standalone runtime can no longer override current Plugin policy, and a missing target cache fails closed.
- The bilingual documentation site, current navigation, recovery guidance, and release tooling now target V7.3.0. V7.2.0 and earlier material remains historical evidence.

## Unchanged safety boundaries

- `execution_authorization=NONE`
- Automatic sub-agents remain limited to Luna / Terra with an automatic ceiling of `gpt-5.6-terra + high`
- Skill activation does not expand file, Git, environment, production, or data authority
- Reviewers cannot finalize their own attribution, and missing cost cannot be treated as zero cost
- Plugin installation continues to fail closed on unverified Codex CLI versions

## Acceptance boundary

Package regression, real-data calibration observation, local Plugin installation, Git commit, remote push, tag, public GitHub Release state, and post-download artifact verification are recorded separately. A PASS at one stage does not substitute for action and readback evidence at another.
