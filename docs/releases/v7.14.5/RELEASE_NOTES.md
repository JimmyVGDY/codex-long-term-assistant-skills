# V7.14.5 发行说明

V7.14.5 将 Codex Desktop 内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.160.0`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归，不构成独立产品支持轨道。

- 冻结 `0.160.0` 至 `0.155.0` 的当前加前十个稳定版窗口；`0.160.0` 进入活动窗口，`0.154.0` 退出并继续失败关闭。
- 登记 0.160.0 的官方 npm integrity、tarball SHA-256、注解标签提交和源码摘要；Hook discovery/schema 与 apply_patch handler/context 合同和 0.159.x 一致，继续复用 `result-v158`，并删除退出版本唯一使用的 `result-v154`。
- 上游 0.160.0 增加项目外 workspace 默认与断线队列恢复，修复 Windows 沙箱、长路径权限及后台控制台窗口，并缓存 Plugin manifest 与远端连接；这些变化不改变本包冻结的 Reviewer 资格、模型默认或 Operation v2 合同。
- 保留 V7.14.4 的 3600 秒有界包验证、master/tag 祖先门禁、Desktop-only 分层验收和公开发行供应链门禁。
- 实际 Codex Desktop 捆绑组件继续由独立 host contract 和新只读进程验收；冻结稳定窗口不等于独立 CLI 产品支持或 Desktop 运行版本声明。

包验证、账户安装、Desktop 新进程、提交、推送、CI、标签、Draft、公开 Release 和匿名下载分别读回。
