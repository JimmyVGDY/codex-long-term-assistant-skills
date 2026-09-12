# V7.9.0 验收记录

English: [Validation record](VALIDATION_REPORT.en.md)

## 已验证候选证据

- Windows 隔离 Codex Home 已完成基础安装、基础升级增强、增强 verify、增强卸载和基础恢复；基础安装不写增强 runtime 或 Hook。
- 定向安装/状态用例、本地化审计、文档一致性、语义检查和差异空白检查在相应候选基线通过。
- 当前账户的状态摘要能区分基础 Plugin 宿主漂移和增强缺失；磁盘 state 不能替代实际宿主加载。

## 尚未完成的发行证据

- 完整包验证、独立复审、Windows/Ubuntu CI、macOS 路径、公开资产、匿名下载、账户升级、Desktop 重启和新任务加载。
- 任何缺少真实环境的组合保持 `UNVERIFIED`，不得推断为支持。

## 状态分离

- `RELEASE_COMPLETE` 与 `INCIDENT_EFFECTIVE` 必须分别报告：前者需要提交、推送、CI、标签、候选/公开资产、匿名下载与隔离安装读回。
- `INCIDENT_EFFECTIVE` 还需要账户安装、必要重启、当前任务加载和现场业务验收。
