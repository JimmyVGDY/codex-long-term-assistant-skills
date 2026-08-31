# Codex 跨项目长期技术助手 V6.6.1 使用说明

## Skill 入口

10 个 Skill 根据任务上下文渐进发现，也可用 `$skill-name` 显式指定：

- Java/JVM：`$java-backend-engineering`
- Python 后端与 AI 服务：`$python-backend-ai-engineering`
- 浏览器与 Renderer：`$frontend-engineering`
- 数据、中间件、存储、GPU、容器与网络：`$data-middleware-ai-infrastructure`
- 日志、Metrics、Trace、Profile：`$log-observability-analysis`
- 行为修改与交付门禁：`$engineering-quality-delivery`
- 风险驱动独立复审：`$multi-agent-independent-review`
- 正式技术文档：`$technical-document-writing`
- 跨会话恢复：`$long-running-task-memory`
- 跨任务复盘与提案治理：`$controlled-evolution-governance`

## Reviewer 与模型策略

Reviewer TOML 不设置 model 和 reasoning effort。协调流程按以下顺序有界选择：

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

自动流程不得超过 Terra High，主 Agent 配置保持不变。

## 实际模型证据

三个字段相互独立：

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

第三项仅为诊断旁证，不能提升为实际模型证明。只有可信、时效有效、可关联到 Hook 事件的宿主证明，才能令 `runtime_model_evidence=VERIFIED`。

## 生命周期与记录

```text
TURN_OPENED -> SUBAGENT_STARTED -> SUBAGENT_STOPPED -> TASK_COMPLETED -> SESSION_ENDED
```

事件采用 TaskOutcomeEvent 2.0，先按 `event_id` 去重，再按 `task_id` 聚合，并按 `project_id + repo_fingerprint` 隔离。SessionEnd 只在 Hook 预算内写入签名队列，封印进程在预算外完成追加和封印。

记录仅含最小结构化元数据，不保存原始 Prompt、完整回答、代码正文、Patch、Token、Cookie、API Key 或凭据。

## 受控演进

Snapshot 与 Assessment 只有通过证据门禁后才能形成 Proposal。Proposal 永久保持 `execution_authorization=NONE`。`ACCEPT` 只允许创建独立实施任务，不授予自动修改、Git、部署、重启、生产或数据写入权限。
