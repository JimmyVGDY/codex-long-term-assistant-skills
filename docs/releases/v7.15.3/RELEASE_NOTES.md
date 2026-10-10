# V7.15.3 发行说明

V7.15.3 将 Codex Desktop 使用的内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.162.1`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归。

- 冻结 `0.162.1` 到 `0.157.0` 的当前加前十个稳定版窗口；`0.162.1` 与 `0.162.0` 进入，`0.156.1` 与 `0.156.0` 退出并继续失败关闭。
- 登记官方 npm integrity、tarball SHA-256、注解标签提交及源码摘要。0.162.x 的 Hook discovery/schema 沿用 0.161.0 合同，但 apply_patch handler 再次漂移，因此新增 `result-v162`；context 未漂移。
- 0.155.1 退出后删除已无消费者的 `result-v155`；既有版本继续按冻结摘要使用 `result-v158` 与 `result-v156`。
- 上游新增 GPT-6.1 Sol 默认目录、MCP 终端登录、语音设备选择及受控 Daybreak/Cyber 入口，并修复权限、恢复与重试路径；这些变化不自动改变本包的模型路由、Reviewer 资格、预算或 Operation v2 合同。
- 包验证、账户 Plugin、真实 Desktop 新任务、提交、推送、CI、注解标签、Draft、公开发行与匿名下载继续独立读回。
