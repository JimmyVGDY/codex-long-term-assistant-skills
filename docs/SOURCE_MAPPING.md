# 源规则到 Codex v3.3 资源的映射

| 来源或新增模块 | Codex 目标 |
|---|---|
| 全局核心规则 | `global/AGENTS.md` |
| Java 后端规则 | `skills/java-backend-engineering/references/java-backend-rules.md` |
| Python 后端与 AI 服务规则 | `skills/python-backend-ai-engineering/references/python-backend-ai-rules.md` |
| 通用前端工程规则 | `skills/frontend-engineering/references/frontend-core-rules.md` |
| 数据、中间件、AI 与基础设施规则 | `skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md` |
| 日志与可观测性分析工作流 | `skills/log-observability-analysis/references/log-observability-analysis-workflow.md` |
| 日志、Metrics、Trace 和多证据源关联模板 | `skills/log-observability-analysis/assets/templates/` |
| 研发质量与交付工作流 | `skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md` |
| 正式技术文档规则 | `skills/technical-document-writing/references/technical-document-writing-rules.md` |
| 文档类型 Playbook | `skills/technical-document-writing/references/document-type-playbooks.md` |
| 12 个正式文档模板 | `skills/technical-document-writing/assets/templates/` |
| 长期任务外部记忆机制 | `skills/long-running-task-memory/references/long-running-task-memory-rules.md` |
| 10 个任务记忆与恢复模板 | `skills/long-running-task-memory/assets/templates/` |
| 持续检查点、安全检查和保留期工具 | `skills/long-running-task-memory/scripts/checkpoint.py` |
| 实施前与实施后多 Agent 复审工作流 | `skills/multi-agent-independent-review/references/multi-agent-independent-review-workflow.md` |
| 实施前审查、复审计划、结果和台账模板 | `skills/multi-agent-independent-review/assets/templates/` |
| 复审轮次、预算和运行时隔离状态控制器 | `skills/multi-agent-independent-review/scripts/review_controller.py` |
| Skill 路由回归用例 | `tests/skill-routing-cases.json` |
| Skill 路由观察评分工具 | `scripts/routing-eval.py` |
| 7 个窄职责 Reviewer（TOML 声明 read-only，运行时隔离另行验证） | `custom-agents/*.toml` |
| Reviewer 运行时隔离说明 | `docs/REVIEWER_RUNTIME_ISOLATION.md` |
| 可选 Agent 并发配置 | `config/agents.example.toml` |

## 职责边界

- `log-observability-analysis`：负责 Logs、Metrics、Trace、Profile、告警和变更事件的横向证据关联与只读边界；
- `engineering-quality-delivery`：控制修改授权、最低验证、Git、CHANGELOG、部署和交付门禁；
- `multi-agent-independent-review`：负责实施前设计门禁、实施后 Reviewer 分工、结果归并、集中修复、定向复核和确定性预算；
- `long-running-task-memory`：负责小节点检查点、任务恢复、单一记忆写入者和交付记录；
- `technical-document-writing`：负责团队正式技术文档、技术方案、设计和报告；
- 自定义 Reviewer：按行为规则完成各自专业审查，不写共享任务文档、不直接修复；系统级只读必须由父会话或运行时证据保证。

## 渐进加载结构

`SKILL.md` 只保留触发范围、强制入口、关键参数和组合边界；详细工作流放入 `references/`，模板放入 `assets/`，辅助工具放入 `scripts/`。这样可避免把全部细则常驻加载到每次任务上下文。
