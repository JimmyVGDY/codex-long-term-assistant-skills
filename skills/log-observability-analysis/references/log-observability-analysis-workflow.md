# 日志与可观测性分析工作流

> V5.0 继续采用 V4.1 引入的按需 Reference。先读取本索引，只加载当前任务需要的分片；不得为了形式一次读取全部文件。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `observability-scope-modes.md` | 职责、输入确认与四种执行模式 | 开始可观测性任务、确认环境和权限模式 |
| `observability-signals.md` | Logs、Metrics、Trace、Profile、告警与变更事件 | 识别和解释不同信号源 |
| `observability-analysis-process.md` | 统一时间线、聚类、关联和根因验证流程 | 执行实际分析和形成证据链 |
| `observability-domain-safety-output.md` | 技术域组合、资源安全、输出和修复切换 | 组合领域 Skill、控制生产风险、输出结论或转入修复 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 跨域任务可以组合多个分片，但应记录每个分片的唯一职责。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、日志和运行结果始终优先于 Reference 中的通用规则。
