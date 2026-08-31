---
name: multi-agent-independent-review
description: >-
  高风险实施前设计与影响审查，或代码、脚本、迁移和运行配置改动后的独立复审、多 Agent 并行审查、六维复审、回归兼容、安全、性能、数据契约、并发状态、测试证据和减少反复回炉时使用。必须区分 Reviewer TOML 的 read-only 声明与运行时真正的系统隔离；简单无行为变化任务不要触发。
---

# 多 Agent 独立复审技能

## 使用范围

本技能包含两个不同门禁：

1. **实施前设计与影响审查**：在高风险方案开始编码前，用 2～4 个不同职责 Reviewer 检查业务边界、契约兼容、安全、数据和性能风险，尽早修正方向；
2. **实施后独立复审**：在形成稳定 `git diff` 并完成最低定向验证后，并行发现问题、统一归因、集中修复和定向复核。

低风险局部修复不机械执行实施前审查；任何复审都不能替代构建、运行测试、数据验证或生产验收。

## 复审隔离等级

Reviewer 的 TOML 中即使声明 `sandbox_mode = "read-only"`，也只能证明**配置意图**，不能单独证明子 Agent 运行时获得了独立只读沙箱。必须区分：

- **Level A：系统隔离复审（system-readonly）**：父会话实际为只读，或受控探针明确被沙箱拒绝；可报告系统级只读；
- **Level B：逻辑只读复审（logical-readonly）**：父会话可写，Reviewer 依靠角色指令不写；具备独立推理价值，但没有系统级写入隔离保证；
- **Level C：实施 Agent 自查（self-review）**：没有独立 Reviewer 上下文，不得冒充独立复审。

严格只读复审默认要求父会话本身运行在只读模式。生产、真实数据、不可逆操作、权限安全和用户明确要求系统隔离时，不得在可写父会话中把逻辑只读写成系统只读。

## 强制执行

1. 开始复审前读取 `references/multi-agent-independent-review-workflow.md`。
2. 确认当前处于实施前 `pre` 还是实施后 `post` 阶段，并明确功能边界、风险级别、证据范围和 Reviewer 预算。
3. 复审前必须记录父会话实际沙箱、Reviewer 配置声明、实际 Agent 类型和可用运行时证据；不得只引用 TOML 就声称系统级只读。
4. 公共 API、数据库迁移、权限模型、核心状态机、跨服务边界、高并发或生产迁移等高风险任务，在编码前优先执行一次实施前审查；默认最多 1 轮、2～4 个 Reviewer。
5. 实施后审查前确认基线 Commit、稳定差异、最低验证结果和可用 Agent 能力。
6. 条件允许时并行启用职责不同的 Reviewer；不得创建职责完全相同的 Reviewer 进行无意义重复扫描。
7. 同一轮 Reviewer 全部返回前，实施 Agent 不得边收问题边零散修改代码。
8. 主协调 Agent 必须去重、合并同根因问题、处理冲突并形成“最小完整修复集合”。
9. 集中修复后只重跑受影响验证和受影响维度复审；修改公共边界时扩大复审范围。
10. 遵守安全上限：最大审查深度 3、实施前最多 1 轮和 4 个 Reviewer、实施后最多 3 轮、最大并行 Reviewer 6、单功能边界累计最多 12 个 Reviewer、最大集中修复 3 轮。
11. 达到深度、轮次、总量或修复上限后停止自动派生，不得伪装成通过；保留阻塞项、未验证项和用户决策点。
12. Reviewer 只报告问题，不修改、提交、推送、部署、重启或执行生产写操作；但在 Level B 中这是行为约束，不是系统隔离保证。
13. 复杂任务优先使用 `scripts/review_controller.py` 持久化轮次、深度、派发、结果、修复、剩余预算和运行时隔离等级，防止上下文压缩后突破限制或误报安全等级。
14. 复审结果需要持续持久化时组合 `$long-running-task-memory`；代码修改、测试和交付门禁组合 `$engineering-quality-delivery`。

## Reviewer 选择

优先使用安装包提供的窄职责自定义 Agent；不可用时使用通用子 Agent，并在任务中明确职责、范围、深度、轮次、预算、隔离等级和输出格式。

- `cp_review_functional_business`
- `cp_review_compatibility_regression`
- `cp_review_security_access`
- `cp_review_performance_resources`
- `cp_review_data_contract`
- `cp_review_state_concurrency`
- `cp_review_test_delivery`

这些 Agent 的 TOML 均声明 `read-only` 并要求禁止写入、提交和继续派生，但运行时是否形成系统级隔离必须独立验证。实施前通常优先从功能业务、兼容契约、安全、性能资源、数据契约中选择 2～4 个；实施后根据实际差异选择 1～6 个，不为凑数量重复审查。

## 资产与脚本

- 实施前审查：`assets/templates/PRE_IMPLEMENTATION_REVIEW.template.md`
- 复审计划：`assets/templates/REVIEW_PLAN.template.md`
- Reviewer 结果：`assets/templates/REVIEW_RESULT.template.md`
- 归并台账：`assets/templates/REVIEW_LEDGER.template.md`
- 隔离证据：`assets/templates/REVIEW_ISOLATION_EVIDENCE.template.md`
- 复审状态控制器：`scripts/review_controller.py`

## 核心原则

> 先确认复审权限边界，再在实施前纠正高成本方向错误；实施后一次发现、统一归因、集中修复、定向复核。独立推理不等于权限隔离，TOML 声明不等于运行时事实。
