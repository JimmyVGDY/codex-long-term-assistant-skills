# V7.7.1 验证报告

English: [VALIDATION_REPORT.en.md](VALIDATION_REPORT.en.md)

- 官方版本门：GitHub 稳定 Release 与 npm `latest` 均为 0.154.0；发布时间分别为 2026-09-09T22:35:38Z 和 2026-09-09T22:40:10.746Z。
- Windows 活动 CLI：同一 npm 全局路径从 0.153.4 更新到 0.154.0；新进程的版本、帮助、登录状态和 Plugin 列表读回通过。
- 兼容注册表：11 个稳定版，锚点 0.154.0，窗口下界 0.150.0；0.149.1、未来版、预发布版与其他窗口外版本失败关闭。
- 官方来源：11/11 Hook async、PreToolUse/PostToolUse schema 与成功 `apply_patch` 结果源码在线摘要复核通过。
- 0.154.0 隔离单元：官方 npm SRI/SHA-256、CLI 合同、隔离 Plugin 往返与合成 Hook 通过。
- 定向单测：兼容注册表与异步 Hook 注册共 19 项通过。
- 完整本地包验证：修复后的最终基线在 Python 3.13.15 下 329 项 package 与 180 项 runtime 回归通过，语义、隐私、路由、载荷和工作树副作用门禁通过。较早一次运行在 Windows 临时 keyring 并发读取时出现 `PermissionError`，该用例单独复跑及后续完整复跑均通过；注册表 digest 约束首次接入时暴露两处旧 attestation 测试夹具，补齐后两项定向测试与最终完整包装器通过。
- 账户安装：事务安装、verify、status、doctor 与 `codex plugin list --json` 读回 Plugin 7.7.1、`installed=true`、`enabled=true`、`HOST_COMPATIBLE`，源码/Marketplace/cache 的 224 文件 payload digest 一致。
- 真实新任务：新的只读 Codex 0.154.0 进程从已安装的 7.7.1 cache 读取 `engineering-quality-delivery` Skill 与 Plugin manifest，输出 `V771_FRESH_HOST_PASS`，Stop Hook 完成。

远端 CI、标签、六份 Release 资产和公开下载读回在相应阶段分别记录；任一未完成时不得由本报告提前推断为通过。
