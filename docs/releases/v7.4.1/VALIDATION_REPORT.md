# V7.4.1 验证报告

状态：最终候选的包级、账户级安装、GitHub 跨平台与真实账户验收均通过；main、标签与公开 Release 状态仍需发布后独立读回。

- 注册表摘要：`1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8`。
- 兼容窗口：0.153.0、0.152.1、0.152.0、0.151.0、0.150.1、0.150.0、0.149.1、0.149.0、0.148.0、0.147.0、0.146.1。
- Windows 本地使用 11 个固定官方 npm 包逐版通过 `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS`。
- schema 3 宿主绑定、同窗口版本漂移、未知版本拒绝、旧 Marketplace 修复和未知元数据保留已有定向回归。
- 完整回归通过 224 项包级测试与 6 项运行时测试；严格双语审计、双语可复现构建以及 494 个已跟踪 Markdown 文件中的 533 个链接检查通过。
- 最终实施后兼容回归与数据契约两名独立 Reviewer 均通过，冻结包 `6fdd3cc363b77715b7852dc398ac0290c5453778d155b205ec5dc444c419573f` 无 Finding。
- Codex 0.153.0 账户级强制重装通过；schema 3、Plugin 激活、宿主绑定和源码/Marketplace/cache 三方 payload 摘要均读回一致：`7fe0aeba4d5d675b2c80ac384a8bd58025c9965fba2a64cafedd047b56ca3b39`。
- GitHub Actions 运行 [33741685461](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33741685461) 对候选提交 `181f5225dccc27abf5dd49712962514f936c5185` 返回 `completed/success`，覆盖 Windows/Ubuntu 的 11 版本兼容矩阵、4 个包验证矩阵和构建证明。
- 真实账户只读验收在 Codex 0.153.0 上使用 Luna Low 完成父子 Agent 旅程，最终输出精确为 `V741_REAL_HOST_PASS`。机器报告确认 7 条事件依次覆盖 `TURN_OPENED`、`PRE_TOOL_GUARD`、`SUBAGENT_STARTED`、子 `TURN_OPENED`、`SUBAGENT_STOPPED`、`TASK_COMPLETED`、`SESSION_ENDED`，请求模型门禁为 `PASS`。
- 普通 Hook payload 未提供受信宿主模型证明，因此实际子 Agent 模型证据保持 `UNAVAILABLE`；真实只读 sandbox 内 DPAPI 封印同样为 `UNAVAILABLE`。`SESSION_ENDED` 已持久化并带 `seal_required=true`，Evolution 对未封印尾部按预期失败关闭，未将其误记为可消费数据。

待发布读回：main 远端提交、`v7.4.1` 标签、标签工作流产物/来源证明和公开 Release。
