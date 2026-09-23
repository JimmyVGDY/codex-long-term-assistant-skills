---
name: multi-agent-independent-review
description: >-
  高风险实施前设计审查、行为改动后的独立复审，或复审前的系统只读隔离门禁核验时使用。普通低风险自查和无行为影响的排版任务不要触发；不要为了形式固定多开 Reviewer。
---

# 多 Agent 独立复审技能

## 入口与阶段边界

- 仅核验复审隔离门禁时，读取相关规则并根据宿主证据报告可用或阻塞；不初始化审查包、台账或派发 Reviewer。读取本 Skill 不证明系统只读，也不授予权限；系统只读为必要条件时，隔离证据不足则停止。
- 对实现行为作独立复审时，保留对应主领域能力。复审流程和质量证据不能替代领域判断；跨阶段记忆按当前恢复或状态维护需要保留，超出默认组合时说明必要性。

下列执行流程适用于门禁满足后的实际复审。

## 强制执行

1. 先读取 `references/multi-agent-independent-review-workflow.md`，只加载当前阶段需要的分片。
2. 分别选择执行流程、统一 DelegationBudget、Reviewer 工作强度和模型档位；Reviewer 只管理轮次与 Finding，不重复扣减总预算。
3. 每次从 Luna Low 的 1 分起算，按复审预算模式和有效证据加分，重算后一次派发。登记 Reviewer 可用十种组合，最高 Astra High；Worker/Explorer 仍为原四档。禁止 xhigh/max/ultra；不得默认直接使用 Sol/Astra，也不为升级先调用低档。规则与权重见 reviewer-model-routing.md。
4. 使用 `review_packet.py` 生成统一审查包并检查 freshness；范围复审额外使用 `scoped_review.py` 绑定目标、静态依赖、配置和权威文件。未知动态依赖必须标为 `INCOMPLETE`，相关指纹变化必须 `STALE`；范围 PASS 不等于全仓发行 PASS。使用 `review_controller.py` 记录隔离、轮次、统一预算 permit 引用、packet hash、模型档位、结果和停止状态。总成本由 `delegation-budget.py` 统一计费。审查包必须与当前 Project ID、Task ID、Git 基线和 Task Envelope 一致。
5. Reviewer 先读摘要和统计，只展开分配范围；同一轮收齐后统一去重、根因聚类和集中修复，不边审边改。
6. 修复后只重跑受影响验证、刷新 packet 并定向复核；相同 Reviewer/相同 packet、无新信息或已无问题通过时停止重复派发。
7. 默认并行不超过 3、累计不超过 6、实施后不超过 2 轮、集中修复不超过 2 轮、Terra High 不超过 1 个；Sol/Astra 合计不超过 2 次、同时 1 个、Astra High 不超过 1 次。所有限制取根预算与控制器更严格者。

## 独立上下文与权限

- 子 Agent 只接收任务边界、差异、约束、证据和未验证项，不复制父会话全部历史。
- 最终只返回结构化 findings、检查范围、未验证项和批准档位、评分引用和隔离证据，不回传原始长日志或内部推理。
- 独立上下文不等于系统只读；父会话可写且没有沙箱拒绝证据时，只能报告 `logical-readonly`。
- Review Evidence 不授予修改、提交、推送、部署或重启权限；修复后基线变化会使旧 packet 和结论失效。

## 工具与资产

- Reviewer 状态：`scripts/review_controller.py`；三类 Agent 总预算：仓库根目录 `scripts/delegation-budget.py`
- 统一审查包与 freshness：`scripts/review_packet.py`
- 范围依赖伴随清单：`scripts/scoped_review.py`
- 结果 Schema：`assets/schemas/review-result.schema.json`
- 模型策略：`references/reviewer-model-routing.md`

> 只在独立判断能增加有效信息时派发 Reviewer；默认从 Luna 起算，由证据和预算决定最终组合。新任务使用 V8/V5/V3 契约，旧任务保留原策略。

## 与受控演进的边界

本 Skill 只产生独立复审 Evidence 和收益归因输入，不维护跨任务演进合同。目标转为 Reviewer 长期收益、模型成本或路由偏差治理时，改由 `controlled-evolution-governance` 处理；单次复审不得因此自动加载演进规则。
