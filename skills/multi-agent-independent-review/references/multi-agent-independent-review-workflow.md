# 多 Agent 独立复审与最少有效修复轮次工作流

> V4.1 将大规则拆为按需 Reference。先读取本索引，只加载当前任务需要的分片；不得为了形式一次读取全部文件。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `review-goals-limits-isolation.md` | 复审目标、预算与运行时隔离 | 开始复审、确定安全上限和隔离等级 |
| `review-triggers-reviewers.md` | 触发条件、风险分级与 Reviewer 分工 | 决定是否复审、选择 Reviewer |
| `review-preimplementation-controller.md` | 实施前审查与状态控制器 | 高风险编码前设计门禁和台账初始化 |
| `review-postimplementation.md` | 实施后审查、并行归并、集中修复与定向复核 | 代码和验证稳定后的 post review |
| `review-stop-output-memory.md` | 停止条件、结构化输出、台账和长期记忆 | 停止自动循环、输出结果、持久化和最终结论 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 跨域任务可以组合多个分片，但应记录每个分片的唯一职责。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、日志和运行结果始终优先于 Reference 中的通用规则。
