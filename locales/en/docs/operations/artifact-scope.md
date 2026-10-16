# Repository gates and task artifact directories

Chinese: [Task artifact directories](artifact-scope.md)

A Codex Desktop chat with an enabled project gate can write fixtures, reports, and other artifacts to an authorized external task directory. Repository code retains Operation v2. External output requires an exact directory registration. Registration is scope metadata with `execution_authorization=NONE`; it does not replace the Desktop sandbox, approval flow, or user authorization, and never returns `permissionDecision: allow`.

## Workflow

1. Prepare a separate output workspace within the authorized task scope and use its absolute path. It must already exist. Do not register a drive root, account home, source repository, or control directory.
2. Attempt the intended native `apply_patch` in the current Desktop chat. An unregistered target returns `ARTIFACT_SCOPE_UNREGISTERED` without writing the file. The Hook freezes the narrowest existing common parent of all targets and returns an AR1 request reference with exact registration parameters. A management command cannot change that scope.
3. Register the directory through the current installed management entry point. The source entry below is for development; installed environments use the same command in the account tools/cp-runtime.py.

```text
python scripts/cp-runtime.py capability-task-artifact-register --profile <project-profile.json> --repo-path <repo> --request-ref <AR1-native-request>
```

The command only consumes a native request record. It accepts no session ID, arbitrary output directory, or lifetime argument, and does not use environment variables to assert session ownership. The request freezes the session, project, directory identity, and deadlines; the command cannot expand that scope. Do not edit state JSON, supply prompt allowlists, or switch writers to evade missing registration.

4. Retry the native patch. Every target must belong to one registered directory. Existing host permissions still decide whether the write is permitted. A neutral Hook response means the repository reuse workflow does not apply; it proves neither artifact quality nor completed execution.
5. Revoke the exact directory when work finishes or scope changes, and read back the result. Revocation does not delete artifacts.

```text
python scripts/cp-runtime.py capability-task-artifact-revoke --profile <project-profile.json> --repo-path <repo> --request-ref <AR1-native-request>
```

Each session/project can register at most 16 non-overlapping directories. A request must be consumed within five minutes; its scope expires 240 minutes after request creation. Replay cannot extend the lifetime, and a revoked request cannot register again. After expiry or directory replacement, recheck authorization and freeze scope through a new native patch request. Returned roots are the actual readback. An interrupted registration remains unusable until its request completes. Revocation invalidates the request before idempotently removing its scope row.

## Boundaries

- A patch cannot mix repository code with external artifacts. Move sources and destinations are checked separately. Relative paths use the native Hook working directory; `..` is rejected.
- Control files, gate state, Profiles, indexes, plugin payloads, control directories of other registered projects, and Git repositories cannot be artifact directories. Account tooling stays protected; specific task output directories under account visualizations remain eligible after the other checks.
- Symbolic links, reparse points, existing multiply linked targets, UNC/device paths, drive-relative paths, ADS, and ambiguous path forms are rejected. Directory, target, ancestor, and processing-time budgets are bounded; uncertainty rejects the affected write.
- Native PreToolUse stores a call binding without patch content. PostToolUse first looks up the original session/turn/tool_use_id, then checks the original cwd and command digest. An external command or changed cwd cannot bypass reconciliation of a dispatched operation.
- Calls dispatched before upgrade without the new binding retain the legacy compatibility path; no new evidence is fabricated. Source changes, package installation, and actual Desktop loading remain distinct states.

## Validation and limits

Local aliases in historical project registrations are resolved only to identify protected controls. Protect both the registered path and its current target; bound alias depth, lookups and time, and reject network aliases or cycles. An unrelated historical junction must not turn an ordinary artifact into a linked write. Actual write targets and ancestors still use the original no-link checks; control-alias resolution never authorizes writing through links.

Directly registered remote roots retain their path boundaries without remote filesystem probes during local write checks. Actual UNC writes and local control aliases that redirect to network paths remain rejected. This does not claim remote-filesystem or cross-host physical-alias verification.

Targeted regressions live in runtime/tests/test_artifact_scope.py, test_patch_intent.py, and test_capability_gate_hook.py. Temporary repositories, synthetic identities, and Hook subprocesses do not prove actual Desktop permission behavior. Report skipped checks separately.

This Hook is not a complete filesystem enforcement boundary and cannot make native writes atomic with prechecks. The host sandbox still controls actual writes; shell/MCP paths are not covered by this claim. See the [official Hooks contract](https://learn.chatgpt.com/docs/hooks).
