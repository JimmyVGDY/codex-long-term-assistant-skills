# V7.4.2 Validation Report

Status: candidate validation is in progress. Local package, the full Windows window, user-level installation, real lifecycle, and independent review are complete; remote CI and public publication remain pending.

- Registry digest: `e2a5e4a19040174c18bbcb66d39e6d349e33fe3c53f7996434a4939b94b0c8f1`.
- Compatibility window: 0.153.2, 0.153.1, 0.153.0, 0.152.1, 0.152.0, 0.151.0, 0.150.1, 0.150.0, 0.149.1, 0.149.0, and 0.148.0.
- All eleven pinned official npm packages pass `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS` locally on Windows.
- Focused regressions cover fail-closed exited versions, `UNAVAILABLE` evidence after a model switch without a fresh trust anchor, and no dispatch-permit or budget consumption by `unified_exec`.
- Complete package validation passes 226 package and 6 runtime tests with the worktree side-effect gate. All 45 routing cases, payload, budget, lifecycle, and model-policy checks pass.
- Strict bilingual audit, 551 links in 494 Markdown files, bilingual site-source generation, and both reproducible ZIPs pass. Exact digests are held by the repository-external build witnesses and post-publication provenance, avoiding a self-reference from packaged documentation to its own artifact digest.
- Codex 0.153.2 user-level forced reinstall passes: version 7.4.2, schema 3, `HOST_COMPATIBLE`, Plugin installed/enabled, and source/Marketplace/cache payload digest `4b9bf790…97679`.
- A real-account read-only parent/child Agent journey on Codex 0.153.2 completed and returned exactly `V742_REAL_HOST_PASS`. The machine report confirms seven events covering `TURN_OPENED`, `PRE_TOOL_GUARD`, `SUBAGENT_STARTED`, the child `TURN_OPENED`, `SUBAGENT_STOPPED`, `TASK_COMPLETED`, and `SESSION_ENDED`; requested-model policy is `PASS`.
- Three logical-readonly independent Reviewers covered compatibility regression, data/state contracts, and test delivery against frozen packet `370c853c…9740f`: zero blocking findings. The only nonblocking item is the intentionally pending remote-CI and publication gates, so the candidate remains `IN_PROGRESS`.
- Ordinary Hook payloads did not provide trusted actual-model evidence, and the DPAPI seal was unavailable. Both remain `UNAVAILABLE`; neither was inferred from the requested model or successful output.

Pending: GitHub Windows/Ubuntu CI, tag, provenance, and public Release readback.
