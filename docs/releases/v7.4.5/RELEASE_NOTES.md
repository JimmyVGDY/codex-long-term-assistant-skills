# V7.4.5 发行说明

版本：7.4.5
主题：Codex CLI 0.153.3 稳定版兼容
宿主窗口：Codex CLI 0.153.3 与此前十个稳定发行版

## 上游变化

- OpenAI Codex CLI 0.153.3 在 Amazon Bedrock 模型选择器中加入 GPT-6-Astra 的 Mantle/Runtime 全球与美国路由。
- Astra 的异步提问说明已修正。
- 这些变化不修改本包已冻结的 Plugin、Marketplace 或 Hook 合同，因此本次采用兼容窗口推进，而不是协议重构。

## 本包变化

- 将闭合兼容注册表锚点推进到 0.153.3，窗口固定为 `0.153.3`、`0.153.2`、`0.153.1`、`0.153.0`、`0.152.1`、`0.152.0`、`0.151.0`、`0.150.1`、`0.150.0`、`0.149.1`、`0.149.0`。
- 固定官方 npm tarball、SRI、SHA-256、CLI help 与 Plugin JSON 证据；0.148.0 退出活动窗口但保留在历史报告中。
- 更新 Windows/Ubuntu 兼容矩阵、安装器、发布验证、双语文档与站点索引到 V7.4.5。
- 自动子 Agent 的批准档位仍仅限 Luna/Terra；GPT-6-Astra 的上游模型选择变化不扩大自动路由策略。

## 本地证据边界

- Windows 原生 CLI 已由同一 npm 全局通道从 0.153.2 更新到 0.153.3，`--help`、登录状态和 Plugin 列表读回通过。
- 0.153.3 官方制品校验、隔离 CLI、Plugin add/list/remove 往返与合成 Hook 已通过。
- V7.4.5 账户级事务安装、`verify`、`status`、`doctor`、Plugin 激活和源码/Marketplace/cache 三方 payload 摘要一致性已通过。
- 实际卸载/回滚与真实父子 Agent 生命周期旅程未执行；远端 CI、标签、资产来源证明和公开 Release 需要后续独立读回。
