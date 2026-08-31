# 源规则到 Codex Skill 的映射

| 来源或新增模块 | Codex 目标 |
|---|---|
| `01-全局核心规则.md` | `global/AGENTS.md` |
| `rules/02-Java后端规则.md` | `skills/java-backend-engineering/references/java-backend-rules.md` |
| `rules/03-Python后端与AI服务规则.md` | `skills/python-backend-ai-engineering/references/python-backend-ai-rules.md` |
| `rules/04-Vue前端工程规则.md` | `skills/vue-frontend-engineering/references/vue-frontend-rules.md` |
| `rules/05-数据中间件与AI工程规则.md` | `skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md` |
| `workflows/01-研发质量与交付工作流.md` | `skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md` |
| `06-长期任务外部记忆机制.md` | `skills/long-running-task-memory/references/long-running-task-memory-rules.md` |
| `templates/*.md` | `skills/long-running-task-memory/assets/templates/` |
| v2.0 新增正式文档规则 | `skills/technical-document-writing/references/technical-document-writing-rules.md` |
| v2.0 新增文档类型 Playbook | `skills/technical-document-writing/references/document-type-playbooks.md` |
| v2.0 新增正式文档模板 | `skills/technical-document-writing/assets/templates/` |

## 职责边界

- `technical-document-writing`：团队正式技术文档、技术方案、设计、报告和 Markdown 重构；
- `engineering-quality-delivery`：代码变更的验证、复审、CHANGELOG、Commit 和环境状态；
- `long-running-task-memory`：Codex 跨会话任务恢复所需的内部计划、进度、决策和交接记录。

`SKILL.md` 只保留触发范围、执行入口、组合方式和关键边界；完整规则放入 `references/`，模板放入 `assets/`，利用渐进式加载降低上下文占用。
