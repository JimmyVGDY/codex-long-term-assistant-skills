# Task Execution Envelope

Task Envelope 是非简单任务的最小确定性控制对象，用于在主会话、独立上下文子 Agent、外部记忆和恢复流程之间传递一致事实。

## 必填字段

- `task_id`、Project ID、Project Profile、仓库根目录与 Project Binding hash；
- `complexity`、`project_stage`、`execution_profile`、`reviewer_budget`、`model_profile`、`host_surface` 六个独立路由维度；
- 目标、非目标、允许范围和禁止范围；
- 主 Skill、支撑 Skill、延迟 Skill 及唯一职责；
- 修改、提交、推送、部署、重启、数据写入和功能生效的独立授权；
- 必须门禁、停止条件、回滚条件和验收标准；
- Git 基线、当前差异指纹、Evidence、Review Packet hash、动作读回和 Finalization 状态。

## 使用规则

1. `LIGHT` 任务可以只在当前响应中维护简化信封；`STANDARD` 和 `STRICT` 建议持久化。
2. 跨会话、受保护操作或长期任务应绑定仓库外 Project Profile；项目 ID、仓库或 Profile hash 不一致时失败关闭。
3. 长任务把信封摘要写入 `CURRENT_TASK.md`，完整机器状态由 `execution_guard.py` 维护。
4. 委派子 Agent 时只发送与其职责相关的信封字段和统一审查包，不复制全部聊天历史。
5. 权限、范围、阶段、基线或 Evidence freshness 变化必须更新信封；旧 Approval、Evidence 和 Review Packet 不得继续沿用。
6. 信封不能覆盖实际代码、Git、配置和运行结果；冲突时进入 `RECOVER` 或 `BLOCKED`。

## 格式版本与所有者

| 对象 | 当前格式 | 事实来源 |
|---|---|---|
| Task Envelope 模板 | schema <!-- cp-fact:schema.envelope -->3<!-- /cp-fact --> | `../assets/templates/TASK_EXECUTION_ENVELOPE.template.yaml` 与包 manifest |
| execution-state | schema <!-- cp-fact:schema.execution-state -->4<!-- /cp-fact --> | `../scripts/execution_guard.py` 的 SCHEMA |
| 嵌入式 delegation_budget 绑定 | schema 1 | execution_guard 的 routing 声明 |
| 外部 DelegationBudget 账本 | <!-- cp-fact:schema.budget -->2.0<!-- /cp-fact --> | 根任务预算运行时 |

这些是不同对象的格式版本，不随包版本一起替换。Reviewer 状态管理复审，不拥有根任务总预算。
