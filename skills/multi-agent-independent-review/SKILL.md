---
name: multi-agent-independent-review
description: >-
  高风险实施前设计审查、行为改动后的独立复审，或复审前的系统只读隔离门禁核验时使用。普通低风险自查和无行为影响的排版任务不要触发；不要为了形式固定多开 Reviewer。
---

# 多 Agent 独立复审技能

## 入口与阶段边界

- 仅核验隔离门禁时，报告实际能力与缺失证据，不因此初始化审查包或派发。没有系统隔离证据时标为 logical-readonly；若用户明确要求系统只读且宿主做不到，只限制该受限审查动作，其他已授权工作继续。
- 对实现行为作独立复审时，保留对应主领域能力。复审流程和质量证据不能替代领域判断；跨阶段记忆按当前恢复或状态维护需要保留，超出默认组合时说明必要性。

下列执行流程适用于门禁满足后的实际复审。

## 强制执行

1. 先读取 `references/multi-agent-independent-review-workflow.md`，只加载当前阶段需要的分片。
2. 分别选择执行流程、统一 DelegationBudget、Reviewer 工作强度和模型档位；Reviewer 只管理轮次与 Finding，不重复扣减总预算。
3. 先读取根任务策略。新默认按[脚本决策与弹性规则](references/script-first-routing.md)选择 GPT-6 九档，信息不足使用 Sol/medium，不要求先取得统计资格；所有角色执行脚本批准的参数。模型保留语义判断，可申请范围内调整。旧 V3/V4 仅按原冻结合同回放或显式兼容，不重算旧账。
4. 使用 `review_packet.py` 生成统一审查包并检查 freshness；范围复审额外使用 `scoped_review.py` 绑定目标、静态依赖、配置和权威文件。未知动态依赖标为 `INCOMPLETE`，并在可读范围继续限定审查；相关指纹变化标为 `STALE` 并刷新受影响材料。范围 PASS 不等于全仓发行 PASS。使用 `review_controller.py` 记录隔离、轮次、统一预算 permit 引用、packet hash、模型档位、结果和停止状态。总成本由 `delegation-budget.py` 统一计费。审查包必须与当前 Project ID、Task ID、Git 基线和 Task Envelope 一致。
5. Reviewer 先读摘要和统计，只展开分配范围；同一轮收齐后统一去重、根因聚类和集中修复，不边审边改。
6. 修复后只重跑受影响验证、刷新 packet 并定向复核；相同 Reviewer/相同 packet、无新信息或已无问题通过时停止重复派发。
7. 新策略由共享账本计算次数、并发、必需预留和允许调整范围；默认并行不超过 3，Astra 同时不超过 1。审查和修复轮次按任务预算收敛，不因缺证据追加完整研究。旧控制器默认累计不超过 6、实施后及修复不超过 2 轮；V3 另限 Terra High 不超过 1 个、Sol/Astra 合计不超过 2 次且同时 1 个、Astra High 不超过 1 次；V4 从固定根资源向量与阶段分配核验各项上限。所有限制取根预算与控制器更严格者。

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
- 新默认与弹性：`references/script-first-routing.md`；旧策略回放：`references/reviewer-model-routing.md`
- V4 管理：仓库根目录 `scripts/routing-v4.py`；根预算 V4、状态 V9、结果 V6、观察样本 V4。

> 需要独立判断时按脚本默认派发，不能把缺历史收益当作不派发的理由；无新信息不重复同包。各版本费用、状态、结果和样本不得混算；同聊天改策略必须记录交接，保留旧调用与迟到事件的归属。

## 与受控演进的边界

本 Skill 只产生独立复审 Evidence 和收益归因输入，不维护跨任务演进合同。目标转为 Reviewer 长期收益、模型成本或路由偏差治理时，改由 `controlled-evolution-governance` 处理；单次复审不得因此自动加载演进规则。
