# Codex 跨项目长期技术助手 V7.2 使用说明

## V7.2 强化项

- 使用 Python 3.11 或更高版本；公开 CI 在 Windows 与 Ubuntu 上验证 3.11 和 3.13。
- `python scripts\validate-package.py` 仅生成包级证据，真实宿主路由状态保持 `NOT_EVALUATED`；完整验证期间仓库索引和文件内容不得变化，`--output` 必须指向仓库外。
- 真实宿主路由使用 `python scripts\routing-eval.py make-host-template` 生成观察模板，再用 `evaluate-host` 校验 11 个全新独立任务及其原始最终报告摘要。预期 Skill 不能反填实际结果。
- 受控演进按信号读取必要证据：模型升级看实际模型覆盖，负面结果看终态覆盖，其他信号不因无关字段缺失而被阻断。
- 受控演进规范以 `$controlled-evolution-governance` 为唯一入口；长期任务记忆和独立复审只保留边界说明。

## 四个主领域

V7 的十个 Skill 仍按任务上下文渐进发现，其中四个主领域按工程职责而非编程语言划分：

- 任意语言服务端、API、事务、并发和 Worker：`$backend-engineering`
- 浏览器、WebView 与 Renderer：`$frontend-engineering`
- 模型、RAG、Agent、AI 评测、推理和多模态生成：`$ai-engineering`
- 数据库、中间件、存储、GPU 资源、容器与网络：`$data-middleware-infrastructure`

六个支撑与工作流 Skill 保持独立：

- 日志、Metrics、Trace、Profile：`$log-observability-analysis`
- 行为修改与交付门禁：`$engineering-quality-delivery`
- 风险驱动独立复审：`$multi-agent-independent-review`
- 正式技术文档：`$technical-document-writing`
- 跨会话恢复：`$long-running-task-memory`
- 跨任务复盘与提案治理：`$controlled-evolution-governance`

每个阶段默认选择一个主领域和最多两个支撑 Skill。跨阶段任务可以更换主领域，不为覆盖整条链路一次加载全部规则。

## 通用后端

`backend-engineering` 先读取通用接口、业务、安全、事务、并发、任务和资源规则，再从项目证据加载一个主要技术栈专项：Java/Spring/JVM、Python Web/async、Node.js、Go、.NET、Rust 或其他后端。

Python 不再与 AI 绑定；普通 Django、FastAPI、Celery 或 Python API 任务只使用通用后端。模型、RAG 或生成链路才组合 AI Skill。

## 通用 AI

`ai-engineering` 不限制实现语言或模型提供方，覆盖：

- 模型调用、流式协议和结构化输出；
- Prompt 注入、数据权限和不可信输出；
- RAG、Embedding、检索权限、引用与评测；
- Agent、工具调用、人工确认和循环上限；
- GPU Worker、多模态生成、任务取消和恢复；
- AI 质量、成本、安全与可观测性。

AI 任务中的语言 SDK、Web API 和 Worker 机制组合通用后端；向量库、MQ、对象存储、GPU 资源与 Kubernetes 组合数据基础设施。

## V6 到 V7 升级

| V6 Skill | V7 路由 |
|---|---|
| `$java-backend-engineering` | `$backend-engineering`，按需加载 Java 专项 |
| `$python-backend-ai-engineering` | 普通后端使用 `$backend-engineering`；模型/RAG/Agent 使用 `$ai-engineering` |
| `$data-middleware-ai-infrastructure` | `$data-middleware-infrastructure`；AI 语义使用 `$ai-engineering` |
| `$vue-frontend-engineering` | `$frontend-engineering` |

V7 不安装兼容别名。安装器只对 Manifest 中声明的受管旧 Skill 执行备份和移除，未知第三方 Skill 保持不变。升级后新旧名称同时出现属于失败状态。

## 安装后读回

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

只有 Plugin 精确读回 `installed=true`、`enabled=true`、`version=7.2.0`，十个新 Skill 可发现、Manifest 声明的四个受管旧 Skill（含此前废弃的 Vue Skill）不再发现时，才可确认升级完成。

## Reviewer 与模型策略

Reviewer TOML 不设置 model 和 reasoning effort。协调流程仍按以下顺序有界选择：

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

自动流程不得超过 Terra High，主 Agent 配置保持不变。Skill 数量、任务复杂度或文件数量不能自动提升模型。

## 生命周期、授权与记录

V7 保留 TaskOutcomeEvent 2.0、`project_id + repo_fingerprint` 隔离、签名事件链、延迟 SessionEnd 封印和 `execution_authorization=NONE` 提案边界。

Evidence 不能授予 Commit、Push、Deploy、Restart、生产操作或数据写入权限。最终交付继续分别报告 modified、validated、reviewed、committed、pushed、deployed、restarted 和 effective。
