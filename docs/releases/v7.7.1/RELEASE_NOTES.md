# V7.7.1 发行说明

English: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

主题：Codex CLI 0.154.0 稳定版兼容

宿主窗口：Codex CLI 0.154.0 与此前十个稳定发行版

- OpenAI Codex CLI 0.154.0 增加 GPT-6-Astra、受管 worktree、异步提问、Windows 后台服务和格式化复制等能力；Plugin 外部升级后可刷新工具、Skill 与 Hook。
- `codex mcp-server` 已从上游移除；本仓库安装、验证与运行链路不依赖该入口。
- 官方 Hook discovery 与 PreToolUse/PostToolUse schema 摘要保持不变；成功 `apply_patch` handler 摘要发生变化，但既有成功输出、PostTool payload 和字符串响应断言仍成立，因此新增独立 `result-v154` profile。
- 闭合兼容窗口前移为 `0.154.0`、`0.153.4`、`0.153.3`、`0.153.2`、`0.153.1`、`0.153.0`、`0.152.1`、`0.152.0`、`0.151.0`、`0.150.1`、`0.150.0`；`0.149.1` 退出活动窗口。
- Plugin、Marketplace、Hook alias、Operation v2、默认关闭门禁和自动子 Agent 的 Luna/Terra 上限保持原合同。
- Windows 实际 CLI 已沿用原 npm 全局渠道从 0.153.4 更新到 0.154.0；版本、帮助、登录状态和 Plugin 列表已由新进程读回。

回滚必须保持宿主与包配对：如需恢复 V7.7.0，先把实际 CLI 恢复为 0.153.4，再通过已有事务安装/恢复入口恢复 V7.7.0；不得让旧包在未知的 0.154.0 宿主上冒充兼容。
