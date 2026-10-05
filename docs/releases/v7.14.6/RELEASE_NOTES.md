# V7.14.6 发行说明

V7.14.6 将 Codex Desktop 使用的内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.160.1`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归，不构成独立产品支持轨道。

- 冻结 `0.160.1` 到 `0.155.1` 的当前加前十个稳定版窗口；`0.160.1` 进入活动窗口，`0.155.0` 退出并继续失败关闭。
- 登记 0.160.1 的官方 npm integrity、tarball SHA-256、注解标签提交和源码摘要。Hook discovery/schema 与 apply_patch handler/context 合同均未漂移，因此 0.160.1 继续复用 `result-v158`；0.155.1 仍使用 `result-v155`。
- 上游 0.160.1 回移 Windows 远程 stdio MCP 环境保留修复，在显式配置远程环境变量时继续传递 `SYSTEMROOT`、`TEMP` 和 `TMP`。该修复不改变本包的 Reviewer 资格、模型默认或 Operation v2 合同。
- 保留 V7.14.5 的有界包验证、master/tag 祖先门禁、Desktop-only 分层验收和公开发行供应链门禁。
- 实际 Codex Desktop 捆绑组件继续通过独立 host contract 与新只读进程验收；冻结稳定版窗口不等于独立 CLI 产品支持或 Desktop 运行版本声明。

包验证、账户安装、Desktop 新进程、提交、推送、CI、标签、Draft、公开 Release 和匿名下载分别读回。
