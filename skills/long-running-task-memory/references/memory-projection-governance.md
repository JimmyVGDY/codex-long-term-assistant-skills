# Checkpoint、Project Memory 与 Knowledge Candidate 治理

## 1. 三层事实边界

| 层级 | 作用 | 可直接复用范围 |
|---|---|---|
| Task Checkpoint | 恢复当前 Task 的阶段、证据、阻塞和下一步 | 当前任务 |
| Project Memory | 经明确审核的项目稳定事实、决策和约束 | 同一 Project |
| Knowledge Candidate | 脱敏后的通用模式候选 | 未审核前不得自动应用 |

Checkpoint、聊天摘要或单个 Reviewer 结论都不能自动成为 Project Memory。

## 2. 晋升链路

```text
Task Checkpoint / Evidence
  → Memory Projection Candidate
  → reviewed_by 明确审核
  → Project Memory
  → 脱敏、适用范围、反例与证据审核
  → Knowledge Candidate
  → 外部治理决定是否激活
```

`cp-runtime.py memory-project` 只生成候选，`memory-promote` 才能写入 Project Memory；`knowledge-candidate` 仍只生成待审记录。

## 3. 候选内容

候选应只包含：

- 已验证事实；
- 已接受决策及原因；
- 稳定约束和风险；
- 未确认项；
- 来源文件、Evidence 或 Checkpoint 引用；
- 适用项目、版本和失效条件。

不得写入明文凭据、私钥、Token、个人敏感信息、完整生产日志或冗长内部推理。

## 4. 失效与冲突

Project Memory 与当前代码、Git、配置或运行结果冲突时，先标记为过期候选并重新验证，不得让历史记忆覆盖当前事实。跨项目候选必须经过适用范围匹配，不能因技术栈名称相同就自动复用。
