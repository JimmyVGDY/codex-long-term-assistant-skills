---
name: long-running-task-memory
description: >-
  任务跨会话、多阶段、多模块、多仓库、多 Agent、生产观察期、上下文可能压缩，或用户要求每个小节点持续更新目标、进度、证据、决策、交接和交付记录时使用。简单一次性任务不要触发。
---

# 长期任务外部记忆与持续检查点技能

## 使用范围

用于跨会话、多阶段、多仓库、多 Agent、生产观察、上下文压缩或必须可靠恢复执行状态的任务。目标是让对话上下文只承担当前节点的短期推理，让确定的本机文档持续保存任务控制状态。

## 强制执行

1. 开始前读取 `references/long-running-task-memory-rules.md`。
2. 确定当前机器可用的 `<AGENT_CONTEXT_ROOT>`；不要写死用户名、操作系统或具体项目路径。
3. 启用本技能后，至少创建或复用 `CURRENT_TASK.md` 和 `PROGRESS.md`；多步骤任务同时维护 `PLAN.md`。
4. 每完成一个“可独立恢复的小节点”，立即追加 `PROGRESS.md` 检查点并刷新 `CURRENT_TASK.md` 当前快照；不得让已完成节点只存在于当前对话中。
5. 尚未形成完整节点但连续执行 5 个实质性动作时，写入“进行中检查点”，防止长时间无持久化状态。
6. 高风险或不可逆操作必须在操作前和操作后分别写检查点。
7. 关键决策、范围外问题、会话交接和实际交付分别更新 `DECISIONS.md`、`KNOWN_ISSUES.md`、`HANDOFF.md` 和 `DELIVERY_RECORD.md`；不要求每次更新全部文档。
8. 多 Agent 场景采用单一写入者：只有主协调 Agent 更新共享记忆；子 Agent 返回结构化结果或写自己被明确分配的独立报告。
9. 恢复任务时先读当前消息和授权，再读任务快照、计划和最近检查点，随后核对实际代码、配置、Git 和运行状态。
10. 文档与实际状态冲突时，以实际状态为准，记录冲突并修正文档。
11. 文档更新不能替代构建、测试、复审、Commit 或生产验证。
12. 多轮、跨服务或持续观察的日志排障可组合 `$log-observability-analysis`；普通一次性单文件分析不机械建立完整外部记忆体系。
13. 外部记忆写入前后都要防止明文凭据、隐私、完整生产连接串和大段原始日志落盘；启用后优先使用 `scripts/checkpoint.py` 的 `security-check` 子命令。
14. 多 Agent 复审检查点必须记录父会话沙箱、Reviewer 配置声明、运行时隔离等级和严格只读资格；逻辑只读不得写成系统隔离。
15. 明确保留期限、归档、同步和删除责任；脚本只生成到期候选报告，不自动删除用户文档。

## 默认参数

```text
MAX_UNPERSISTED_COMPLETED_NODES = 0
MAX_SUBSTANTIVE_ACTIONS_WITHOUT_CHECKPOINT = 5
RECENT_CHECKPOINTS_TO_LOAD = 5
HOT_PROGRESS_CHECKPOINT_LIMIT = 30
SINGLE_MEMORY_WRITER = true
CHECKPOINT_BEFORE_HIGH_RISK_ACTION = true
CHECKPOINT_AFTER_HIGH_RISK_ACTION = true
DEFAULT_COMPLETED_TASK_RETENTION_DAYS = 90
DEFAULT_TEMPORARY_ANALYSIS_RETENTION_DAYS = 30
EXTERNAL_MEMORY_SECRET_SCAN = true
```

项目级规则或用户要求设置更严格值时，采用更严格值。

## 模板与辅助脚本

模板位于 `assets/templates/`：

- `PROJECT_CONTEXT.template.md`
- `CURRENT_TASK.template.md`
- `PLAN.template.md`
- `PROGRESS.template.md`
- `DECISIONS.template.md`
- `HANDOFF.template.md`
- `KNOWN_ISSUES.template.md`
- `DELIVERY_RECORD.template.md`
- `CHECKPOINT_ENTRY.template.md`
- `RECOVERY_CHECKLIST.template.md`

可选辅助脚本：`scripts/checkpoint.py`。它使用 Python 标准库提供 `init`、`append`、`validate`、`recover`、`repair`、`archive`、`security-check`、`secure` 和 `retention-report`，通过写入锁、原子替换、Git 指纹和热区归档降低共享状态损坏风险；Python 不可用时按同一规则手工维护。

## 边界

- 外部记忆必须保存在 Agent 专用目录，不得进入项目仓库、Git、项目 CHANGELOG 或正式工程文档。
- Linux/WSL 目录建议权限 700、文档和状态文件建议 600；Windows 必须确认目录 ACL 仅允许当前用户和受信任管理员访问。
- 不默认同步到 OneDrive、NAS、公共云盘或其他设备；备份与同步必须符合公司安全策略并由用户明确决定。
- 只记录可验证事实、证据等级、授权、修改、命令、测试、复审、阻塞、风险和下一步；不记录冗长内部推理。
- Codex 内置 Memories 或 Chronicle 只能作为辅助召回层，不替代当前任务的确定性检查点和项目硬规则。
- 项目正式技术方案、架构文档、部署手册和管理报告使用 `$technical-document-writing`。
