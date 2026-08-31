---
name: multi-agent-independent-review
description: >-
  高风险实施前设计审查，或行为改动后的独立复审、多 Agent 并行审查、回归兼容、安全、性能、数据契约、并发状态和测试证据审查时使用。简单低风险或无行为变化任务不要触发。
---

# 多 Agent 独立复审技能

## 独立上下文模型

- Codex 子 Agent 可在独立上下文中执行专门任务；探索、证据收集和中间工具输出留在子 Agent 内，仅把结构化结论返回主会话。
- 主协调 Agent 不应复制整个父会话历史，只提供最小审查包：任务边界、基线、差异、约束、已执行验证、相关文件和未验证项。
- **上下文独立不等于权限隔离。** Codex Reviewer 仍必须区分系统只读、逻辑只读和未验证；TOML 声明不能替代实际运行时证据。

## 强制执行

1. 先读取 `references/multi-agent-independent-review-workflow.md` 索引，只加载当前 pre/post 阶段所需分片。
2. 选择 `LIGHT / STANDARD / STRICT` 复审强度和 `economy / balanced / deep` Reviewer 成本档位。
3. 派发前使用 `scripts/review_packet.py` 生成统一审查包，并使用 `scripts/review_controller.py` 记录阶段、轮次、深度、预算、隔离证据和 packet hash。
4. 同一轮全部 Reviewer 返回前不边审边改；主 Agent 统一去重、根因聚类和冲突裁决，形成最小完整修复集合。
5. 修复后只重跑受影响验证和定向复核；公共契约变化时扩大范围。
6. 达到深度、轮次、并发、总量或修复上限后停止自动循环，保留阻塞项和未验证项。

## 工具与资产

- 复审状态：`scripts/review_controller.py`
- 统一审查包：`scripts/review_packet.py`
- Reviewer 结构化结果 Schema：`assets/schemas/review-result.schema.json`
- 复审强度与成本：`references/reviewer-effort-tiers.md`

## 核心原则

> 用独立上下文隔离噪声，用统一审查包约束事实基线，用结构化结果降低主会话负担；独立推理不等于系统级只读。
