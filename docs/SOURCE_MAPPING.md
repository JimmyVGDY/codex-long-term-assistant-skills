# 源规则到 Codex V5.0 资源的映射

| 规则或能力 | Codex V5.0 目标 |
|---|---|
| 全局跨项目边界、授权和模型路由 | `global/AGENTS.md` |
| Java 后端 | `skills/java-backend-engineering/` |
| Python 后端与 AI 服务 | `skills/python-backend-ai-engineering/` |
| 通用前端工程 | `skills/frontend-engineering/` |
| 数据、中间件、AI 与基础设施 | `skills/data-middleware-ai-infrastructure/` |
| 日志与可观测性 | `skills/log-observability-analysis/` |
| 研发质量、执行信封与证据指纹 | `skills/engineering-quality-delivery/` |
| 技术文档与正式报告 | `skills/technical-document-writing/` |
| 长期记忆、检查点去重与恢复 | `skills/long-running-task-memory/` |
| 多 Agent 独立复审 | `skills/multi-agent-independent-review/` |
| Luna/Terra 模型策略 | `docs/MODEL_ROUTING_AND_COST_POLICY.md` |
| Codex `[agents]` 配置 | `config/agents.example.toml`、`docs/CODEX_CONFIG_GUIDE.md` |
| 7 个窄职责 Reviewer | `custom-agents/*.toml` |
| Reviewer 模型路由 | `skills/multi-agent-independent-review/references/reviewer-model-routing.md` |
| 审查包与 freshness | `skills/multi-agent-independent-review/scripts/review_packet.py` |
| 预算、重复派发和模型审计 | `skills/multi-agent-independent-review/scripts/review_controller.py` |
| 检查点内容去重 | `skills/long-running-task-memory/scripts/checkpoint.py` |
| 路由回归 | `tests/skill-routing-cases.json`、`scripts/routing-eval.py` |
| 包结构、语义与隔离安装验证 | `scripts/validate-package.py`、`scripts/semantic-lint.py` |

## 职责边界

- `LIGHT/STANDARD/STRICT` 管执行和交付门禁；
- `economy/balanced/deep` 管 Reviewer 数量与上下文预算；
- 四级模型档位管单个子 Agent 的模型和推理强度；
- 主 Agent 是唯一协调者和共享记忆写入者；
- Reviewer 只做窄职责、渐进读取和结构化返回；
- `sandbox_mode = "read-only"` 不是运行时系统隔离证明。

`SKILL.md` 只保留触发条件、强制入口、成本边界和组合关系；详细规则放在 `references/`，模板放在 `assets/`，可执行护栏放在 `scripts/`。
