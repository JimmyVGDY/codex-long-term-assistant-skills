# 长期任务外部记忆、持续检查点与知识晋升机制

> V5.0 继续采用按需 Reference，并把 Task Checkpoint、Project Memory 和 Cross-project Knowledge 明确分层。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `memory-principles-layout.md` | 外部记忆原则、目录与文档职责 | 启用长期记忆、初始化目录和选择文档 |
| `memory-checkpoints.md` | 启用条件、小节点、检查点事务与高风险双检查点 | 任务推进、持久化节点、写前写后检查点 |
| `memory-projection-governance.md` | Checkpoint 投影、项目记忆晋升和知识候选 | 需要沉淀稳定项目事实或跨项目经验 |
| `memory-multiagent-events.md` | 多 Agent 单写者与事件型文档更新 | 并行 Agent、Reviewer 结果和计划/决策/交接更新 |
| `memory-recovery-conflicts.md` | 恢复协议与状态冲突处理 | 上下文压缩、会话恢复、项目/分支/代码/文档冲突 |
| `memory-security-lifecycle.md` | 仓库隔离、精简、安全、保留和归档 | 敏感信息、权限、生命周期、归档和完成复核 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- Task Checkpoint 只负责当前任务恢复；Project Memory 只保存经审核的本项目稳定事实；Knowledge Candidate 只是待审跨项目候选。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、Git、日志和运行结果始终优先于记忆中的历史记录。
