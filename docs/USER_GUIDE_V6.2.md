# Codex 跨项目长期技术助手 V6.2 使用说明

## 1. 文档信息

- 适用版本：V6.2.0
- 主要目标环境：Windows 原生 Codex CLI 0.150.1
- 推荐安装方式：账户级 Plugin 模式
- 适用读者：需要使用 Codex 处理多技术栈工程任务、独立复审、长期任务和受控演进的开发者

## 2. 这个包是什么

V6.2 不是需要单独启动的桌面软件，也不是业务项目模板。它是安装到 Codex 中的工程工作流增强包，包含：

- 10 个工程 Skills；
- 7 个专业 Reviewer；
- 6 个生命周期 Hooks；
- TaskOutcomeEvent V2 与事件哈希链；
- 长期任务检查点与项目外部记忆；
- 受控 Evolution Snapshot、Assessment 和 Proposal 流程；
- 安装、备份、验证、回滚和卸载工具。

安装后仍然像平常一样在 Codex 中打开项目并使用自然语言交代任务。Agent 会按任务类型渐进加载合适的 Skill；不需要每次手工运行包内脚本。

## 3. 安装或从 V6.1 升级

### 3.1 前置条件

在 PowerShell 中确认：

```powershell
codex --version
python --version
```

V6.2 的目标 Codex 版本为 `0.150.1`。Windows 原生安装路径应为：

```text
C:\Users\<account-name>\.codex
```

如果进程继承了 `/mnt/c/Users/.../.codex`，安装器会转换为 Windows 原生盘符路径；不要把 WSL 风格路径作为 Windows 原生安装目标。

### 3.2 解压

不要直接修改或在 ZIP 内运行。示例：

```powershell
Expand-Archive -LiteralPath .\Codex-Skills-V6.2.zip -DestinationPath .\Codex-Skills-V6.2-unpacked
Set-Location .\Codex-Skills-V6.2-unpacked\Codex-Skills-V6.2
```

### 3.3 环境检查

```powershell
python scripts\package_manager.py doctor
```

确认输出中的 `version` 为 `6.2.0`、`target_codex` 与实际 `codex_version` 均为 0.150.1，并检查 `codex_home` 是否为 Windows 原生路径。

### 3.4 dry-run

```powershell
python scripts\package_manager.py install --scope user --mode plugin --dry-run
```

检查：

- 是否识别当前旧版本；
- 是否会创建时间戳备份；
- 目标是否只位于 `.codex` 和 cp-assistant Marketplace 允许范围；
- 是否存在 Junction、Reparse Point 或符号链接阻断；
- 是否存在外部修改漂移；
- 是否有未知文件会被覆盖。

### 3.5 正式升级

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python scripts\package_manager.py install --scope user --mode plugin
```

安装器会准备 Marketplace、Reviewer 和全局规则，并调用 Codex Plugin/Marketplace 命令完成注册。文件复制完成不等于 Plugin 已激活。

### 3.6 验证

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

目标 Plugin 必须满足：

```text
pluginId = codex-cross-project-engineering-assistant@cp-assistant-local
installed = true
enabled = true
version = 6.2.0
```

升级完成后，关闭并重新打开升级前已存在的 Codex App、CLI 或 IDE 任务。无需重启 Windows。

## 4. 日常使用

最常见的方式是直接描述任务：

```text
检查这个项目的登录接口为什么偶尔返回 500。
先只读分析代码和日志，确认根因，不要修改代码。
```

```text
修复订单重复提交问题。
先确认调用链和数据边界，然后实施最小修复、运行定向测试，
最后根据风险安排必要的独立 Reviewer。
不要提交、推送或部署。
```

Agent 会从当前代码、配置、日志、测试和任务授权出发选择 Skill，不会因为安装了全部能力就同时加载所有 Skill。

## 5. 10 个 Skills

| Skill | 适用任务 |
|---|---|
| `java-backend-engineering` | Java、Spring、JVM、Maven、事务、并发、SSE |
| `python-backend-ai-engineering` | Python、FastAPI、Django、Flask、异步、Celery、AI/RAG/GPU Worker |
| `frontend-engineering` | JavaScript/TypeScript、React、Vue、Angular、Svelte、浏览器和 Renderer |
| `data-middleware-ai-infrastructure` | SQL、Redis、MQ、ES、对象存储、GPU、Docker、Kubernetes、网络 |
| `log-observability-analysis` | 日志、Metrics、Trace、Profiling、告警和变更事件 |
| `engineering-quality-delivery` | 修改、测试、Git、发布、回滚、审批和最终交付 |
| `multi-agent-independent-review` | 高风险实施前审查和行为改动后的独立复审 |
| `technical-document-writing` | 技术方案、架构、接口、部署、故障和正式报告 |
| `long-running-task-memory` | 跨会话、多阶段、多模块、多 Agent 和上下文压缩任务 |
| `controlled-evolution-governance` | 跨任务复盘、自观察、成本路由、Reviewer 收益和 Proposal 治理 |

通常让 Agent 自动路由即可。需要明确约束时，可以直接写：

```text
使用 $python-backend-ai-engineering 检查这个 FastAPI 服务的并发问题。
先分析，不要修改。
```

```text
使用 $frontend-engineering 修复这个 React 页面状态不同步问题，
并使用 $engineering-quality-delivery 完成测试和交付验证。
```

每个阶段默认一个主领域 Skill，必要时组合质量、日志、复审、文档或长期任务 Skill；不建议为了形式同时指定全部 Skill。

## 6. 7 个 Reviewer

| Reviewer | 职责 |
|---|---|
| `cp_review_functional_business` | 功能正确性与业务口径 |
| `cp_review_compatibility_regression` | 原有功能回归与兼容性 |
| `cp_review_security_access` | 认证、鉴权、越权、注入和敏感信息 |
| `cp_review_performance_resources` | SQL、I/O、连接、线程、队列和资源负担 |
| `cp_review_data_contract` | 数据库、API、Redis、MQ、序列化和一致性边界 |
| `cp_review_state_concurrency` | 竞态、幂等、超时、重试、取消和状态边界 |
| `cp_review_test_delivery` | 测试证据、失败项、文档和交付边界 |

让 Agent 自动选择：

```text
修复完成后，根据真实风险选择必要的独立 Reviewer 做只读复审，
不要为了形式全部启动。
```

明确指定：

```text
启动 cp_review_security_access，使用 Luna Low，
只读检查鉴权、越权和敏感信息风险。
```

Reviewer TOML 不写死模型。自动模型成本路线为：

```text
Luna Low -> Luna Medium -> Terra Medium -> Terra High
```

自动流程最高 Terra High。显式 Sol、`xhigh/max/ultra`、未知模型或无法证明不超过上限的模型会被 PreToolUse Hook 拒绝。

## 7. 长期任务和检查点

普通一次性任务只记录最小生命周期事件。跨会话、多阶段、多模块或多 Agent 任务应使用长期任务记忆：

```text
这是一个长期任务。
使用 $long-running-task-memory 管理目标、计划、授权、证据、风险和检查点。
每完成一个可独立恢复的阶段写一次检查点，持续到全部验收完成。
```

长期任务至少维护：

```text
CURRENT_TASK.md
PROGRESS.md
PLAN.md
```

恢复任务时：

```text
恢复上次长期任务，读取当前任务、当前计划阶段和最近三个检查点，
再核对当前 Git、代码和运行状态后继续。
```

检查点只保存可验证事实、证据、授权、状态、风险和下一步，不保存冗长内部推理。Task Checkpoint 不会自动晋升为项目记忆或跨项目知识。

## 8. 自动自观察记录什么

六个 Hook 自动记录：

```text
UserPromptSubmit -> TURN_OPENED
PreToolUse       -> PRE_TOOL_GUARD
SubagentStart    -> SUBAGENT_STARTED
SubagentStop     -> SUBAGENT_STOPPED
Stop             -> TASK_COMPLETED
SessionEnd       -> SESSION_ENDED
```

TaskOutcomeEvent V2 保存最小结构化元数据，例如：

- event/session/turn/task ID；
- `project_id + repo_fingerprint`；
- 实际模型和推理强度；
- Reviewer、发现项和修复轮次计数；
- 明确的终态；缺少明确结果时为 `UNKNOWN`；
- 前向 SHA-256 哈希链，可选 HMAC。

默认不会保存原始 Prompt、完整回答、代码正文、Diff、Token、Cookie、API Key 或其他凭据。安装 V6.2 以前没有记录的数据不会自动补写。

## 9. 受控演进与复盘

受控演进只用于跨任务复盘、Reviewer 收益、模型成本、Skill 路由偏差和助手自身版本治理，不用于普通编码。

推荐提示词：

```text
使用 $controlled-evolution-governance，
分析这个项目近期的 Event、Checkpoint、Review 和 Evidence，
生成 Snapshot、Assessment 和 Optimization Proposal。
只生成提案，不自动接受或实施。
```

标准链路：

```text
Lifecycle Event
  -> Task 聚合
  -> Self Observation Snapshot
  -> Value / Complexity Assessment
  -> Optimization Proposal
  -> 人工 ACCEPT / REJECT / DEFER
  -> ACCEPT 后另建实施任务
  -> 独立验证并关闭 Proposal
```

如果复盘证据不足，Agent 必须标记 `UNKNOWN`、列出证据缺口或停止生成 Proposal，不能从普通 `status` 猜测成败，也不能借用其他项目的数据。

无论 Proposal 状态如何，`execution_authorization` 永远为 `NONE`。人工 ACCEPT 只认可优化方向，不授权文件修改、提交、推送、部署或生产操作。

## 10. 权限和安全边界

包内工作流不会自动获得以下权限：

- 修改业务代码、Skill、Reviewer、路由或全局配置；
- 接受或执行 Evolution Proposal；
- Git commit 或 push；
- 部署、重启或使功能生效；
- 修改数据库或生产数据；
- 操作生产环境。

已取得明确授权某个动作时，仍需要绑定当前项目、任务、环境和基线，并在动作后读回实际状态。测试证据不能替代操作授权。

## 11. 推荐任务模板

```text
请处理以下任务：

目标：
[描述问题或交付物]

执行约束：
1. 先确认项目、技术栈、调用链、数据边界和当前基线。
2. 先给出根因或实施计划，再进行最小充分修改。
3. 不修改无关文件，不顺手升级无关依赖。
4. 完成定向测试和必要的回归验证。
5. 根据风险选择必要的独立 Reviewer。
6. 最终分别报告：已修改、已验证、已复审、已提交、
   已推送、已部署、已重启、已生效。
7. 未经授权不要提交、推送、部署、重启或操作生产环境。
```

## 12. 维护、验证与故障排查

检查 Plugin：

```powershell
codex plugin list --json
```

重新验证安装：

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
```

验证发行包自身：

```powershell
python scripts\validate-package.py
python scripts\routing-eval.py validate
```

常见问题：

### Plugin 文件存在但未启用

以 `codex plugin list --json` 为准。重新运行安装器或执行安装器输出的 Marketplace/Plugin 注册步骤，不能仅根据文件复制判断成功。

### Windows Hook 找不到 Python

V6.2 无需 `python3.exe`。确认本机账户 Python、PATH 中的 `python.exe` 或 Python Launcher `py.exe` 至少有一个可用。

### 中文 Stop 或 Hook 输出异常

确认实际 Plugin 版本为 6.2.0，并检查六个 Hook 是否通过 `cp_hook.cmd` 启动。升级前已打开的 Codex 任务需要关闭后重开。

### 项目事件没有进入聚合

确认记录的 `project_id` 和 `repo_fingerprint` 同时匹配。任一不一致都会按安全策略拒绝聚合。

### 历史任务缺少复盘数据

V6.2 不回填安装前事件。使用现有 Git、日志、测试、旧检查点和 Evidence；不足部分标记为未验证。从后续长期任务开始明确启用长期任务记忆。

## 13. 卸载和恢复

查看卸载计划：

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin --dry-run
```

正式卸载：

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin
```

卸载会按升级备份恢复受管文件；检测到外部修改时默认拒绝覆盖。只有确认希望覆盖受管漂移后才使用 `--force`。

项目上下文、自观察 Event、Snapshot、Assessment、Proposal 和历史备份不会随普通卸载自动删除。

## 14. 验收清单

- [ ] `codex --version` 为目标版本 0.150.1
- [ ] `doctor` 显示 V6.2.0 和正确 Windows CODEX_HOME
- [ ] dry-run 无路径、Reparse Point、漂移或回滚阻断
- [ ] 正式安装退出码为 0
- [ ] `verify --mode plugin` 通过
- [ ] Plugin 为 installed=true、enabled=true、version=6.2.0
- [ ] 10 个 Skills 可发现
- [ ] 7 个 Reviewer 可发现且未写死模型
- [ ] 6 个 Hook 可加载，SessionEnd timeout=3 秒
- [ ] 不需要创建 `python3.exe`
- [ ] 主 Agent 模型配置未被覆盖
- [ ] 历史项目上下文和升级备份仍保留

