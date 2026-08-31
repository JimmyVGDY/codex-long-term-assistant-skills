# V5.0 权威事实源注册表

## 1. 原则

同一事实只允许一个权威 Owner。其他文件可以引用或生成投影，但不能成为第二个可覆盖版本。

| 事实 | 唯一 Owner | 允许的投影 |
|---|---|---|
| 包版本、Skill、Reviewer、上限 | `manifest.json` | README、Skill Matrix、校验报告 |
| 项目身份和稳定边界 | `project-profile.json` | Onboarding 报告、任务信封引用 |
| 项目当前阶段和基线 | `project-state.json` | 状态摘要 |
| 任务阶段、门禁、Evidence、动作 | `execution-state.json` | Finalization Report、Handoff |
| Reviewer 调度和预算 | `review-state.json` | Review Ledger |
| Review 冻结输入 | Review Packet `manifest.json` | Packet Summary |
| 当前任务恢复 | `CURRENT_TASK.md` + `PROGRESS.md` | Recovery Summary |
| 项目长期事实 | `project-memory.md` | 项目文档引用 |
| 跨项目经验候选 | Knowledge Candidate JSON | 人工评估报告 |

## 2. 状态冲突处理

- 机器状态与 Markdown 冲突：优先机器状态，并记录冲突；
- 项目文档与实际 Git/运行结果冲突：优先当前可验证事实；
- Checkpoint 与 Project Memory 冲突：Checkpoint 只说明任务当时状态，不能覆盖已审核项目事实；
- Knowledge Candidate 与当前项目事实冲突：候选只作为输入，不能自动应用；
- Approval 与 Evidence 冲突：两者职责不同，不能互相替代。

## 3. 文档状态

建议文档显式标记：

- `active`：当前适用规范；
- `reference`：按需读取资料；
- `historical`：仅用于追溯；
- `generated`：由机器状态生成，可重新生成。

历史文档不得覆盖 Active 规则，Generated 文档不得被当作独立事实源手工维护。
