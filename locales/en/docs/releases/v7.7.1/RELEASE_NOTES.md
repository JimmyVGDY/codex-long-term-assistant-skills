# V7.7.1 Release Notes

Chinese: [Chinese documentation](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/zh-CN/docs/releases/v7.7.1/RELEASE_NOTES/)

Theme: Codex CLI 0.154.0 stable compatibility

Host window: Codex CLI 0.154.0 plus the ten preceding stable releases

- OpenAI Codex CLI 0.154.0 adds GPT-6-Astra, managed worktrees, asynchronous questions, a Windows background server, and formatting-preserving copy; externally upgraded Plugins can refresh tools, Skills, and Hooks.
- Upstream removed `codex mcp-server`; this repository's install, validation, and runtime paths do not depend on that entry point.
- The official Hook discovery and PreToolUse/PostToolUse schema digests are unchanged. The successful `apply_patch` handler digest changed while the existing successful-output, PostTool-payload, and string-response assertions remain valid, so this release adds a dedicated `result-v154` profile.
- The closed compatibility window advances to `0.154.0`, `0.153.4`, `0.153.3`, `0.153.2`, `0.153.1`, `0.153.0`, `0.152.1`, `0.152.0`, `0.151.0`, `0.150.1`, and `0.150.0`; `0.149.1` exits the active window.
- Plugin, Marketplace, Hook aliases, Operation v2, the default-disabled gate, and the Luna/Terra automatic-subagent ceiling retain their existing contracts.
- The effective Windows CLI was updated through the existing global npm channel from 0.153.4 to 0.154.0; a fresh process read back version, help, login status, and the Plugin list.

Rollback must keep host and package versions paired. To restore V7.7.0, first restore the effective CLI to 0.153.4 and then restore V7.7.0 through the existing transactional installation/recovery path. The old package must not be presented as compatible with an unknown 0.154.0 host.
