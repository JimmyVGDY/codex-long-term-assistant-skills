---
name: long-running-task-memory
description: >-
  任务跨会话、多阶段、多模块、多仓库、多 Agent、生产观察期、上下文可能压缩，或用户要求持续维护计划、进度、决策、交接和交付记录时使用。简单一次性任务不要触发。
---

# 长期任务外部记忆技能

## 使用范围

用于跨会话、多阶段、多仓库、多 Agent、生产观察、上下文压缩或必须可靠恢复执行状态的任务。简单任务不得为了形式创建全部文档。

## 执行步骤

1. 读取 `references/long-running-task-memory-rules.md`。
2. 确定当前机器可用的 `<AGENT_CONTEXT_ROOT>`；不要在规则中写死用户名和操作系统路径。
3. 只创建任务实际需要的文档，模板位于 `assets/templates/`：
   - `PROJECT_CONTEXT.template.md`
   - `CURRENT_TASK.template.md`
   - `PLAN.template.md`
   - `PROGRESS.template.md`
   - `DECISIONS.template.md`
   - `HANDOFF.template.md`
   - `KNOWN_ISSUES.template.md`
   - `DELIVERY_RECORD.template.md`
4. 外部记忆必须保存在 Agent 专用目录，不得进入项目仓库、Git、项目 CHANGELOG 或正式工程文档。
5. 只记录已确认事实、证据等级、授权、修改、命令、测试、复审、阻塞、风险和下一步；不记录冗长内部推理。
6. 恢复任务时，先读当前用户消息和授权，再读任务文档，最后重新检查实际代码、配置、Git 和运行状态。
7. 文档与实际状态冲突时，以实际状态为准并修正文档。
8. 文档更新不能替代构建、测试、复审、Commit 或生产验证。

## 边界

- 不机械创建全部模板。
- 不把计划状态“已完成”当成任务完成证据。
- 不把密码、Token、隐私、完整日志或大段源码写入外部记忆。
