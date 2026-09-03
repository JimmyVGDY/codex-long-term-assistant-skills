# V7.4.1 发行说明

版本：7.4.1  
宿主窗口：Codex CLI 0.153.0 与此前十个稳定发行版

## 主要变化

- 新增闭合的 `config/codex-compatibility-v1.json` 注册表，按稳定发行版计数并固定 11 个官方制品、能力 profile 与证据状态。
- Plugin 安装前在隔离 `CODEX_HOME` 完成 Marketplace 添加、Plugin 激活、JSON 读回和卸载，不使用真实账户凭据。
- 安装状态升级为 schema 3，绑定 Codex 版本、CLI 路径与 SHA-256、注册表摘要、能力摘要和 payload 摘要。
- `verify`、`status` 与 `doctor` 检测版本、可执行文件、注册表或能力漂移，并返回 `HOST_DRIFT_REINSTALL_REQUIRED`。
- Marketplace 合并只覆盖本包管理的名称、显示名与目标 Plugin 条目，保留未知顶层、`interface` 子字段、`owner` 和其他 Plugin。
- Hook 明确登记 snake_case、camelCase 与兼容别名；安全字段冲突失败关闭，观察字段冲突记为不可用；Stop 与 SubagentStop 始终返回合法中性 JSON。
- SessionEnd Hook 只构造有上限且不含正文的净化事件，并通过命令参数无等待派发 detached worker，不再扫描或写入事件链，也不再同步写管道；Worker 在 Hook 预算外统一校验稳定生命周期身份，完成语义去重、持久化、DPAPI 解密、绑定 `event_id` 的 v2 签名入队与封印。所有入口拒绝缺失稳定 ID 的事件，未封印的 `seal_required` 链不会进入 Evolution。
- GitHub 发布门禁在 Windows 与 Ubuntu 上逐一重放 11 个稳定版本。

## 不变边界

- Reviewer、Explorer、Worker 的统一根任务预算、模型权重和父级校准规则保持 V7.4.0 口径。
- 自动模型最高仍为 `gpt-5.6-terra + high`，不自动使用 Sol、`xhigh`、`max` 或 `ultra`。
- 普通 Hook 字段不构成可信实际模型证明；不记录 Prompt、回答、代码、Diff、Token 或凭据。
- 未登记的未来版、预发布版与窗口外版本在 Plugin 模式失败关闭，可显式使用 standalone 模式。

## 证据边界

本地 Windows 隔离矩阵不等于 GitHub Ubuntu CI 或真实账户会话。发布前仍须分别读回完整包验证、CI、独立复审、0.153.0 真实账户安装与 Hook 证据。
