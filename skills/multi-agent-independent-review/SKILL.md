---
name: multi-agent-independent-review
description: >-
  高风险实施前设计与影响审查，或代码、脚本、迁移和运行配置改动后的独立复审、多 Agent 并行审查、六维复审、回归兼容、安全、性能、数据契约、并发状态、测试证据和减少反复回炉时使用。Reviewer 默认只读；简单无行为变化任务不要触发。
---

# 多 Agent 独立复审技能

## 使用范围

本技能包含两个不同门禁：

1. **实施前设计与影响审查**：在高风险方案开始编码前，用 2～4 个不同职责 Reviewer 检查业务边界、契约兼容、安全、数据和性能风险，尽早修正方向；
2. **实施后独立复审**：在形成稳定 `git diff` 并完成最低定向验证后，并行发现问题、统一归因、集中修复和定向复核。

低风险局部修复不机械执行实施前审查；任何复审都不能替代构建、运行测试、数据验证或生产验收。

## 强制执行

1. 开始复审前读取 `references/multi-agent-independent-review-workflow.md`。
2. 确认当前处于实施前 `pre` 还是实施后 `post` 阶段，并明确功能边界、风险级别、证据范围和 Reviewer 预算。
3. 公共 API、数据库迁移、权限模型、核心状态机、跨服务边界、高并发或生产迁移等高风险任务，在编码前优先执行一次实施前审查；默认最多 1 轮、2～4 个 Reviewer。
4. 实施后审查前确认基线 Commit、稳定差异、最低验证结果和可用 Agent 能力。
5. 条件允许时并行启用职责不同的只读 Reviewer；不得创建职责完全相同的 Reviewer 进行无意义重复扫描。
6. 同一轮 Reviewer 全部返回前，实施 Agent 不得边收问题边零散修改代码。
7. 主协调 Agent 必须去重、合并同根因问题、处理冲突并形成“最小完整修复集合”。
8. 集中修复后只重跑受影响验证和受影响维度复审；修改公共边界时扩大复审范围。
9. 遵守安全上限：最大审查深度 3、实施前最多 1 轮和 4 个 Reviewer、实施后最多 3 轮、最大并行 Reviewer 6、单功能边界累计最多 12 个 Reviewer、最大集中修复 3 轮。
10. 达到深度、轮次、总量或修复上限后停止自动派生，不得伪装成通过；保留阻塞项、未验证项和用户决策点。
11. Reviewer 只报告问题，不修改、提交、推送、部署、重启或执行生产写操作。
12. 复杂任务优先使用 `scripts/review_controller.py` 持久化轮次、深度、派发、结果、修复和剩余预算，防止上下文压缩后突破限制。
13. 复审结果需要持续持久化时组合 `$long-running-task-memory`；代码修改、测试和交付门禁组合 `$engineering-quality-delivery`。

## Reviewer 选择

优先使用安装包提供的只读自定义 Agent；不可用时使用通用只读子 Agent，并在任务中明确职责、范围、深度、轮次、预算和输出格式。

- `cp_review_functional_business`
- `cp_review_compatibility_regression`
- `cp_review_security_access`
- `cp_review_performance_resources`
- `cp_review_data_contract`
- `cp_review_state_concurrency`
- `cp_review_test_delivery`

实施前通常优先从功能业务、兼容契约、安全、性能资源、数据契约中选择 2～4 个；实施后根据实际差异选择 1～6 个，不为凑数量重复审查。

## 资产与脚本

- 实施前审查：`assets/templates/PRE_IMPLEMENTATION_REVIEW.template.md`
- 复审计划：`assets/templates/REVIEW_PLAN.template.md`
- Reviewer 结果：`assets/templates/REVIEW_RESULT.template.md`
- 归并台账：`assets/templates/REVIEW_LEDGER.template.md`
- 复审状态控制器：`scripts/review_controller.py`

## 核心原则

> 先在实施前纠正高成本方向错误，再在实施后一次发现、统一归因、集中修复、定向复核；追求最少有效修复轮次，不为了“一次修完”掩盖新发现的真实阻塞问题。
