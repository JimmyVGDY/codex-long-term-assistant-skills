# 多 Agent 独立复审与成本收敛工作流

> V4.2 采用渐进式加载。先读本索引，只加载当前阶段和风险需要的 Reference；不得一次读取全部规则。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `review-goals-limits-isolation.md` | 目标、默认预算、硬上限和运行时隔离 | 启动复审或确定安全边界 |
| `reviewer-model-routing.md` | Luna/Terra 四级模型路由和升级条件 | 计划或派发 Reviewer |
| `reviewer-effort-tiers.md` | `economy/balanced/deep` 数量与上下文预算 | 选择复审规模 |
| `review-triggers-reviewers.md` | 触发条件、风险级别和 Reviewer 职责 | 决定是否复审和选择角色 |
| `review-preimplementation-controller.md` | 实施前门禁与状态控制器 | 高风险编码前 |
| `review-postimplementation.md` | 统一审查包、并行归并、集中修复与定向复核 | 差异和最低验证稳定后 |
| `review-stop-output-memory.md` | 停止、结构化结果、台账和长期记忆 | 归并、关闭和持久化 |

## 最小加载原则

- 当前步骤只加载一个主 Reference；确有跨域需要时再加载第二个。
- Skill、Reference 和项目规则只提供方法，不替代实际代码、配置、日志和运行证据。
- Reviewer 先读 packet 摘要和范围统计，证据不足时再展开完整 diff 与依赖。
- 已完成阶段的细则不继续常驻活动上下文；主会话只保留结构化摘要和证据索引。
