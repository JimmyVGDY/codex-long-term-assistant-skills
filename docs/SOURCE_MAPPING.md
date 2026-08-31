# 源规则到 Codex v3.0 资源的映射

| 来源或新增模块 | Codex 目标 |
|---|---|
| 全局核心规则 | `global/AGENTS.md` |
| Java 后端规则 | `skills/java-backend-engineering/references/java-backend-rules.md` |
| Python 后端与 AI 服务规则 | `skills/python-backend-ai-engineering/references/python-backend-ai-rules.md` |
| Vue 前端工程规则 | `skills/vue-frontend-engineering/references/vue-frontend-rules.md` |
| 数据、中间件、AI 与基础设施规则 | `skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md` |
| 研发质量与交付工作流 | `skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md` |
| 正式技术文档规则 | `skills/technical-document-writing/references/technical-document-writing-rules.md` |
| 文档类型 Playbook | `skills/technical-document-writing/references/document-type-playbooks.md` |
| 12 个正式文档模板 | `skills/technical-document-writing/assets/templates/` |
| 长期任务外部记忆机制 | `skills/long-running-task-memory/references/long-running-task-memory-rules.md` |
| 10 个任务记忆与恢复模板 | `skills/long-running-task-memory/assets/templates/` |
| 持续检查点辅助工具 | `skills/long-running-task-memory/scripts/checkpoint.py` |
| v3.0 多 Agent 独立复审工作流 | `skills/multi-agent-independent-review/references/multi-agent-independent-review-workflow.md` |
| 复审计划、结果和台账模板 | `skills/multi-agent-independent-review/assets/templates/` |
| 7 个专业只读 Reviewer | `custom-agents/*.toml` |
| 可选 Agent 并发配置 | `config/agents.example.toml` |

## 职责边界

- `engineering-quality-delivery`：控制修改授权、最低验证、Git、CHANGELOG、部署和交付门禁；
- `multi-agent-independent-review`：负责 Reviewer 分工、并行复审、结果归并、集中修复和定向复核；
- `long-running-task-memory`：负责小节点检查点、任务恢复、单一记忆写入者和交付记录；
- `technical-document-writing`：负责团队正式技术文档、技术方案、设计和报告；
- 自定义 Reviewer：只读执行各自专业审查，不写共享任务文档，不直接修复。

## 渐进加载结构

`SKILL.md` 只保留触发范围、强制入口、关键参数和组合边界；详细工作流放入 `references/`，模板放入 `assets/`，辅助工具放入 `scripts/`。这样可避免把全部细则常驻加载到每次任务上下文。
