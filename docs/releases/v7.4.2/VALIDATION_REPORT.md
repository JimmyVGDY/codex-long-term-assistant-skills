# V7.4.2 验证报告

状态：最终候选的包级、账户级安装、GitHub 跨平台、真实账户生命周期和独立复审均通过；main 最终证据提交、标签与公开 Release 状态仍需发布后独立读回。

- 注册表摘要：`e2a5e4a19040174c18bbcb66d39e6d349e33fe3c53f7996434a4939b94b0c8f1`。
- 兼容窗口：0.153.2、0.153.1、0.153.0、0.152.1、0.152.0、0.151.0、0.150.1、0.150.0、0.149.1、0.149.0、0.148.0。
- Windows 本地 11 个固定官方 npm 包逐版通过 `CLI_CONTRACT_PASS + ISOLATED_PLUGIN_PASS + SYNTHETIC_HOOK_PASS`。
- 定向回归已覆盖退出窗口失败关闭、模型切换无可信新证明时保持 `UNAVAILABLE`，以及 `unified_exec` 不消费派发许可与预算。
- 完整包验证通过 226 项 package 与 6 项 runtime 测试，工作树副作用门禁通过；45 个路由场景、payload、预算、生命周期与模型策略均通过。
- 严格双语审计、503 个 Markdown 文件中的 557 个链接、双语文档源和两份可复现 ZIP 通过；精确摘要由仓库外构建 witness 与发布后的来源证明记录，避免包内文档自引用制品摘要。
- Codex 0.153.2 账户级强制重装通过：7.4.2、schema 3、`HOST_COMPATIBLE`、Plugin 已安装启用，源码/Marketplace/cache payload 摘要均为 `4b9bf790…97679`。
- Codex 0.153.2 真实账户只读验收完成父子 Agent 旅程并精确返回 `V742_REAL_HOST_PASS`；机器报告确认 7 条事件覆盖 `TURN_OPENED`、`PRE_TOOL_GUARD`、`SUBAGENT_STARTED`、子 `TURN_OPENED`、`SUBAGENT_STOPPED`、`TASK_COMPLETED` 和 `SESSION_ENDED`，请求模型策略为 `PASS`。
- 三名逻辑只读独立 Reviewer 完成冻结包 `370c853c…9740f` 的兼容回归、数据/状态契约与测试交付复审：0 个阻塞 Finding；最初的唯一非阻塞项是远程 CI 与发布门禁，CI 已完成，标签和公开发布继续按顺序读回。
- 普通 Hook payload 未提供可信实际模型证明，DPAPI 封印也不可用；二者均保持 `UNAVAILABLE`，未从请求模型或成功输出反推宿主事实。
- GitHub Actions 兼容矩阵运行 [33831782447](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33831782447) 对候选提交 `b997edcf5384ae86720fabb53abb03bb02f66a37` 返回 `completed/success`，22/22 个 Windows/Ubuntu 兼容单元全部成功。
- GitHub Actions 持续集成运行 [33831782428](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/33831782428) 对同一候选返回 `completed/success`，4 个 Python 3.11/3.13 × Windows/Ubuntu 包验证与 1 个双语构建任务共 5/5 成功；链接检查与文档站工作流同样成功。

待发布读回：main 最终证据提交、`v7.4.2` 标签、标签工作流产物/来源证明和公开 Release。
