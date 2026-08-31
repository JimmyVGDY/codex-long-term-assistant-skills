# 源文件到 Codex Skill 的映射

| 原模块 | Codex 目标 |
|---|---|
| `01-全局核心规则.md` | `global/AGENTS.md` |
| `rules/02-Java后端规则.md` | `skills/java-backend-engineering/references/java-backend-rules.md` |
| `rules/03-Python后端与AI服务规则.md` | `skills/python-backend-ai-engineering/references/python-backend-ai-rules.md` |
| `rules/04-Vue前端工程规则.md` | `skills/vue-frontend-engineering/references/vue-frontend-rules.md` |
| `rules/05-数据中间件与AI工程规则.md` | `skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md` |
| `workflows/01-研发质量与交付工作流.md` | `skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md` |
| `06-长期任务外部记忆机制.md` | `skills/long-running-task-memory/references/long-running-task-memory-rules.md` |
| `templates/*.md` | `skills/long-running-task-memory/assets/templates/` |

`SKILL.md` 只保留触发范围、执行入口、组合方式和关键边界；完整细则放入 `references/`，避免技能启用时无条件加载不必要模板。
