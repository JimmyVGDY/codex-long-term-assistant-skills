---
name: long-running-task-memory
description: >-
  任务跨会话、多阶段、多模块、多仓库、多 Agent、生产观察期、上下文可能压缩，或要求持续维护目标、进度、证据、决策和交接时使用。简单一次性任务不要触发，也不要为无状态工具调用重复写检查点。
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

## 模型与委派成本

- 本 Skill 默认不派生子 Agent；读取、格式整理、检查点、投影候选和交接摘要属于 `luna-low` 或 `luna-medium`。
- 复杂技术冲突由对应领域 Skill 使用 Terra 判断，记忆 Skill 只持久化已审核结论，不重复推理。

## 工具与边界

- 当前任务检查点：`scripts/checkpoint.py`
- 项目记忆投影、晋升和知识候选：安装后的 `cp-runtime.py`，源码入口为包根目录 `scripts/cp-runtime.py`
- 外部记忆不得进入项目仓库、Git、项目变更记录或正式工程文档。
- 不记录冗长内部推理，只记录可验证事实、证据等级、授权、状态、阻塞、风险和下一步。

<!-- V6.0-CONTROLLED-EVOLUTION:BEGIN -->
## V6.0 自观察与受控自进化

当任务目标是复盘长期失败、模型升级、Reviewer 收益、修复轮次、Skill 路由偏差或跨任务成本时：

1. 先确认 Project ID 和仓库外项目上下文；
2. 使用 `python3 -B scripts/evolution.py run ... --dry-run`；
3. 只依据结构化 Feedback、Review、Evidence、Checkpoint 和 Audit 生成观察快照；
4. 数据满足阈值后才能形成价值/复杂度评估和优化提案；
5. 所有提案 `execution_authorization=NONE`；
6. 人工 ACCEPT 也不等于执行授权；
7. 真正修改必须另建任务并经过现有 Execution Guard、Review Packet 和 Finalization。

详细规则按需读取 `references/controlled-self-evolution.md`，不要在普通任务中加载全部 Evolution 文档。
<!-- V6.0-CONTROLLED-EVOLUTION:END -->
