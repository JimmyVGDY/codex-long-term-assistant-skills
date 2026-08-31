---
name: multi-agent-independent-review
description: >-
  代码改动后的独立复审、多 Agent 并行审查、六维复审、回归与兼容、安全、性能、数据契约、并发状态、测试证据或减少反复回炉修复次数时使用。Reviewer 默认只读；简单无行为变化任务不要触发。
---

# 多 Agent 独立复审技能

## 使用范围

用于已经形成稳定 `git diff` 的代码、脚本、Worker、调度、迁移、导出或运行配置变更。目标是一次并行发现尽可能完整的问题集，统一归因后集中修复，再对受影响范围定向复核。

## 强制执行

1. 开始复审前读取 `references/multi-agent-independent-review-workflow.md`。
2. 确认功能边界、基线 Commit、差异范围、最低验证结果、风险级别和可用 Agent 能力。
3. 条件允许时优先并行启用职责不同的只读 Reviewer；不得创建多个职责完全相同的 Reviewer 进行无意义重复扫描。
4. 第一轮 Reviewer 全部返回前，实施 Agent 不得边收问题边零散修改代码。
5. 主协调 Agent 必须去重、合并同根因问题、处理冲突并形成“最小完整修复集合”。
6. 集中修复后，只重跑受影响验证和受影响维度复审；修改公共边界时扩大复审范围。
7. 遵守默认上限：最大审查深度 3、最大复审轮次 3、最大并行 Reviewer 6、单功能边界最多 12 个 Reviewer。
8. 达到深度、轮次或总量上限后停止自动派生，不得伪装成通过；保留阻塞项、未验证项和用户决策点。
9. Reviewer 只报告问题，不修改、提交、推送、部署、重启或执行生产写操作。
10. 复审结果需要持久化时组合 `$long-running-task-memory`；代码修改、测试和交付门禁组合 `$engineering-quality-delivery`。

## Reviewer 选择

优先使用安装包提供的只读自定义 Agent；不可用时使用通用只读子 Agent，并在任务中明确职责、范围、深度、轮次、预算和输出格式。

- `cp_review_functional_business`
- `cp_review_compatibility_regression`
- `cp_review_security_access`
- `cp_review_performance_resources`
- `cp_review_data_contract`
- `cp_review_state_concurrency`
- `cp_review_test_delivery`

## 资产

- 复审计划：`assets/templates/REVIEW_PLAN.template.md`
- Reviewer 结果：`assets/templates/REVIEW_RESULT.template.md`
- 归并台账：`assets/templates/REVIEW_LEDGER.template.md`

## 核心原则

> 一次发现、统一归因、集中修复、定向复核；追求最少有效修复轮次，不为了“一次修完”掩盖新发现的真实阻塞问题。
