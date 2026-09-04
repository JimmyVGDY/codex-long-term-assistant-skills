# V7.4.2 Validation Report

Status: the final candidate passes package validation, user-level installation, GitHub cross-platform validation, real-account lifecycle, and independent review. The final evidence commit on main, tag, and public Release still require post-publication readback.

- Registry digest: `e2a5e4a19040174c18bbcb66d39e6d349e33fe3c53f7996434a4939b94b0c8f1`.
- Compatibility window: 0.153.2, 0.153.1, 0.153.0, 0.152.1, 0.152.0, 0.151.0, 0.150.1, 0.150.0, 0.149.1, 0.149.0, and 0.148.0.
- All eleven pinned official npm packages pass `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS` locally on Windows.
- Focused regressions cover fail-closed exited versions, `UNAVAILABLE` evidence after a model switch without a fresh trust anchor, and no dispatch-permit or budget consumption by `unified_exec`.
- Complete package validation passes 226 package and 6 runtime tests with the worktree side-effect gate. All 45 routing cases, payload, budget, lifecycle, and model-policy checks pass.
- Strict bilingual audit, 557 links in 503 Markdown files, bilingual site-source generation, and both reproducible ZIPs pass. Exact digests are held by the repository-external build witnesses and post-publication provenance, avoiding a self-reference from packaged documentation to its own artifact digest.
- Codex 0.153.2 user-level forced reinstall passes: version 7.4.2, schema 3, `HOST_COMPATIBLE`, Plugin installed/enabled, and source/Marketplace/cache payload digest `4b9bf790…97679`.
- A real-account read-only parent/child Agent journey on Codex 0.153.2 completed and returned exactly `V742_REAL_HOST_PASS`. The machine report confirms seven events covering `TURN_OPENED`, `PRE_TOOL_GUARD`, `SUBAGENT_STARTED`, the child `TURN_OPENED`, `SUBAGENT_STOPPED`, `TASK_COMPLETED`, and `SESSION_ENDED`; requested-model policy is `PASS`.
- Three logical-readonly independent Reviewers covered compatibility regression, data/state contracts, and test delivery against frozen packet `370c853c…9740f`: zero blocking findings. The sole initial nonblocking item covered remote CI and publication gates; CI is complete, while the tag and public publication remain ordered readbacks.
- Ordinary Hook payloads did not provide trusted actual-model evidence, and the DPAPI seal was unavailable. Both remain `UNAVAILABLE`; neither was inferred from the requested model or successful output.
- GitHub Actions compatibility run [33831782447](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33831782447) returned `completed/success` for candidate `b997edcf5384ae86720fabb53abb03bb02f66a37`; all 22 Windows/Ubuntu compatibility cells passed.
- GitHub Actions CI run [33831782428](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33831782428) returned `completed/success` for the same candidate; all four Python 3.11/3.13 × Windows/Ubuntu package jobs and the bilingual build job passed (5/5). Link-check and documentation-site workflows also succeeded.

Pending publication readback: the final evidence commit on main, the `v7.4.2` tag, tag-workflow artifacts/provenance, and the public Release.
