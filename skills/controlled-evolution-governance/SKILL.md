---
name: controlled-evolution-governance
description: >-
  仅在跨任务复盘、自观察数据治理、模型成本路由、Reviewer 收益评估、Skill 路由偏差、优化提案生命周期、项目隔离或长期技术助手自身版本治理时使用。普通编码、普通 Review、单次故障排查不要触发。
---

# 受控演进与项目治理

## 使用边界

1. 只处理结构化观测事实、统计、证据引用与优化提案，不直接修改其他 Skill、Reviewer、路由策略、业务仓库或生产环境。
2. 所有 Optimization Proposal 必须保持 `execution_authorization=NONE`。
3. 人工 `ACCEPT` 只表示“允许建立实施任务”，不等于授予文件写入、Git 提交、推送、部署或生产操作权限。
4. 观察必须按 `project_id + repo_fingerprint` 双重隔离；任一不一致立即拒绝聚合。
5. 原始事件先按 `event_id` 去重，再按 `task_id` 聚合；同一 Task 不得因生命周期事件数量更多而被重复加权。
6. 终态结果只使用 `PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN`；禁止从通用 `status` 猜测任务成败。
7. 自动 Reviewer、Explorer、Worker 共用根任务预算且最高 Terra High；显式 Sol 或 `xhigh/max/ultra` 由 Hook 前置拒绝，实际启动模型仍要靠可信宿主证明核验。
8. Hook 只采集最小结构化元数据，禁止保存原始 Prompt、完整回答、代码正文、Patch、Token、Cookie、API Key 或其他凭据。

## 标准流程

```text
Lifecycle Hooks
    ↓
TaskOutcomeEvent V2
    ↓ event_id 去重
Task 聚合
    ↓ project_id + repo_fingerprint 隔离
Self Observation Snapshot
    ↓
Value / Complexity Assessment
    ↓
Optimization Proposal
    ↓
人工 ACCEPT / REJECT / DEFER
    ↓ ACCEPT 后另建实施 Task
正常 Approval / Git Baseline / Review / Validation
    ↓
关闭 Proposal
```

详细契约按需读取：

- `references/task-outcome-event-v2.md`
- `references/proposal-lifecycle-v6.md`

## 模型与成本原则

治理分析默认先使用 Luna 处理机械聚合与读取，只有涉及跨任务语义冲突、高风险策略裁决时逐级升到 Terra；自动最高 `gpt-5.6-terra + high`，禁止用更强模型掩盖数据质量或路由问题。

DelegationBudget 校准只消费主协调 Agent 已最终化、项目身份完整且实际模型可信的样本。离线回放不足最低样本时必须返回“不调整”；任何建议都保持 `execution_authorization=NONE`，不得直接修改预算或路由。
