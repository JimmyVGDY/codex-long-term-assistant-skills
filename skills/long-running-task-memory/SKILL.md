---
name: long-running-task-memory
description: >-
  任务跨会话、多阶段、多模块、多仓库、多 Agent、生产观察期、上下文可能压缩，或需持续维护目标、进度、证据、决策和交接时使用。简单一次性任务不要触发，也不要为无状态工具调用重复写检查点。
---

# 长期任务外部记忆与持续检查点技能

## 执行原则

1. 先读取 `references/long-running-task-memory-rules.md`，只加载当前阶段需要的记忆分片。
2. 任务控制状态、授权、Evidence 和下一步保存到仓库外的 Agent 专用目录；代码、Git、配置和运行结果仍是技术事实真相。
3. 最少维护 `CURRENT_TASK.md` 和 `PROGRESS.md`；多步骤任务再维护 `PLAN.md`，其他文档按事件创建。
4. 采用事件驱动检查点：完成可恢复节点立即写；尚未成节点时，连续 8 个实质动作才写进行中检查点。
5. `checkpoint.py append` 对同一工作区和相同内容自动去重；只有确需保留重复快照时才使用 `--force-append`。
6. 高风险操作前后双检查点；上下文压缩、会话切换或暂停前刷新 `HANDOFF.md`。
7. 多 Agent 采用单一写入者；子 Agent 只返回结构化结果，不直接更新共享记忆。
8. 恢复时读取当前任务、计划当前阶段和最近 3 个检查点，再核对 Project Binding、Git 与运行状态；活跃检查点超过 20 条时归档旧记录。
9. Task Checkpoint 不能自动进入 Project Memory；先按 `references/memory-projection-governance.md` 生成 Projection Candidate，经明确审核后晋升。
10. 单项目记忆不能自动成为跨项目知识；必须脱敏、声明适用范围、保留反例和来源证据，再形成待审 Knowledge Candidate。
11. 记忆写入前后执行凭据扫描、权限检查和生命周期治理。
12. 首次非简单开发接管、恢复已有能力索引或维护公共模块记录时，按[能力索引开发流程](../engineering-quality-delivery/references/capability-index-workflow.md)执行。索引只保存可失效的事实定位，任务摘要链接ID与证据；主协调者增量合并，稳定记忆仍须投影和人工审核。

## 模型与委派成本

主 Agent 保持当前选择。子 Agent 的型号、思考强度和预算采用[脚本决策与弹性规则](../multi-agent-independent-review/references/script-first-routing.md)；执行脚本返回的精确参数。

- 新默认覆盖 GPT-6 Luna、Sol、Astra 的 low/medium/high；信息不足采用 Sol/medium，不以缺少理由、收益卡或历史样本阻止派发。
- 模型保留语义判断和调整建议；脚本在既有权限、总预算和允许调整范围内重新计算后才改变调用参数。规模或单次检查失败不直接代表难度，也不必然升档。
- 可计算的读取、去重、计数、预留和重试交脚本。缺证据走默认/降级路径，允许继续与验证通过分开记录。
- 复杂技术冲突由对应领域 Skill 形成结论；记忆 Skill 只持久化已审核事实，默认串行维护，不为记忆操作单独派发。

## 工具与边界

- 当前任务检查点：`scripts/checkpoint.py`
- 项目记忆投影、晋升和知识候选：安装后的 `cp-runtime.py`，源码入口为包根目录 `scripts/cp-runtime.py`
- 外部记忆不得进入项目仓库、Git、项目变更记录或正式工程文档。
- 不记录冗长内部推理，只记录可验证事实、证据等级、授权、状态、阻塞、风险和下一步。

## 与受控演进的边界

本 Skill 只为跨任务分析提供已审核的 Checkpoint 和恢复证据，不维护演进合同。目标转为跨任务失败、模型成本、Reviewer 收益或 Skill 路由偏差治理时，改由 `controlled-evolution-governance` 处理；普通长期任务不要加载演进规则。
