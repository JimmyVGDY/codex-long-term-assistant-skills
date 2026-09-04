# TaskOutcomeEvent V3

V3 records lifecycle state, project isolation, approved dispatch profile, permit reference, reserved cost, and outcome metrics only. It does not read, infer, persist, or export host runtime model identity or reasoning effort.

## Write boundary

- New chains write V3 only. V2 chains remain immutable, separately stored, and read-only verified.
- Metadata recursively removes model identity, reasoning effort, prompts, responses, code, diffs, credentials, and secret fields.
- One chain cannot mix V2 and V3.
- A `project_id + repo_fingerprint` mismatch fails closed.

## Legacy projection

Raw V2 records are first verified against their original schema, SHA-256, and optional HMAC. Only lifecycle, project identity, terminal outcome, and review counts are then projected. Legacy model identity fields and nested copies cannot reach snapshots, proposals, verification reports, or release attestations.

## Authority

Events prove observations only. They grant no authority to edit, commit, push, deploy, restart, write data, or execute a proposal.
