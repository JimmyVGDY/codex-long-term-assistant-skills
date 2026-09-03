---
name: multi-agent-independent-review
description: >-
  高风险实施前设计审查，或行为改动后的独立复审、回归兼容、安全、性能、数据契约、并发状态和测试证据审查时使用。简单低风险、证据充分或无行为变化任务不要触发，也不要为了形式固定多开 Reviewer。
---

# 多 Agent 独立复审技能

## 强制执行

1. 先读取 `references/multi-agent-independent-review-workflow.md`，只加载当前阶段需要的分片。
2. 分别选择执行流程、统一 DelegationBudget、Reviewer 工作强度和模型档位；Reviewer 只管理轮次与 Finding，不重复扣减总预算。
3. 自动模型按 `luna-low -> luna-medium -> terra-medium -> terra-high` 逐级路由，最高为 Terra High；禁止自动使用 Sol、`xhigh`、`max` 或 `ultra`。
4. 使用 `review_packet.py` 生成统一审查包并检查 freshness；使用 `review_controller.py` 记录隔离、轮次、统一预算 permit 引用、packet hash、模型档位、结果和停止状态。总成本由 `delegation-budget.py` 统一计费。审查包必须与当前 Project ID、Task ID、Git 基线和 Task Envelope 一致。
5. Reviewer 先读摘要和统计，只展开分配范围；同一轮收齐后统一去重、根因聚类和集中修复，不边审边改。
6. 修复后只重跑受影响验证、刷新 packet 并定向复核；相同 Reviewer/相同 packet、无新信息或已无问题通过时停止重复派发。
7. 默认并行不超过 3、累计不超过 6、实施后不超过 2 轮、集中修复不超过 2 轮、Terra High 不超过 1 个；显式放宽也不得超过控制器硬上限。

## 独立上下文与权限

- 子 Agent 只接收任务边界、差异、约束、证据和未验证项，不复制父会话全部历史。
- 最终只返回结构化 findings、检查范围、未验证项和模型/隔离证据，不回传原始长日志或内部推理。
- 独立上下文不等于系统只读；父会话可写且没有沙箱拒绝证据时，只能报告 `logical-readonly`。
- Review Evidence 不授予修改、提交、推送、部署或重启权限；修复后基线变化会使旧 packet 和结论失效。

## 工具与资产

- Reviewer 状态：`scripts/review_controller.py`；三类 Agent 总预算：仓库根目录 `scripts/delegation-budget.py`
- 统一审查包与 freshness：`scripts/review_packet.py`
- 结果 Schema：`assets/schemas/review-result.schema.json`
- 模型策略：`references/reviewer-model-routing.md`

> 只在独立判断能增加有效信息时派发 Reviewer；用 Luna 承担读取密集和机械核验，用 Terra 承担业务与高风险判断。

## 与受控演进的边界

本 Skill 只产生独立复审 Evidence 和收益归因输入，不维护跨任务演进合同。目标转为 Reviewer 长期收益、模型成本或路由偏差治理时，改由 `controlled-evolution-governance` 处理；单次复审不得因此自动加载演进规则。
