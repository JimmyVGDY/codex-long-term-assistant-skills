# Codex 跨项目长期技术助手 V6.5 使用说明

## 1. 适用场景

V6.5 用于长期维护多个软件项目，适合以下任务：

- 阅读现有代码、配置、日志和测试后给出证据化结论；
- 实施 Java、Python、前端、数据、中间件、AI 基础设施等改动；
- 管理修改、验证、复审、提交、推送、部署和回滚之间的授权边界；
- 在跨会话任务中维护目标、计划、证据、风险和检查点；
- 通过独立 Reviewer 检查功能、兼容、安全、性能、数据合同、状态并发和交付证据；
- 基于最小生命周期事件进行跨任务复盘和受控优化提案。

安装后无需为普通任务执行额外初始化。直接在目标仓库打开新的 Codex 任务并描述目标、范围和授权即可。

## 2. 安装状态确认

```powershell
codex --version
codex plugin list --json
```

目标状态：

```text
codex-cli 0.150.1
plugin id = codex-cross-project-engineering-assistant@cp-assistant-local
installed = true
enabled = true
version = 6.5.0
```

重新验证：

```powershell
python scripts\package_manager.py verify --scope user --mode plugin
```

升级前已经打开的任务可能继续持有旧 Plugin 快照。升级后新建任务完成 Skill、Reviewer 和 Hook 的最终发现验证。

## 3. 最小使用方式

普通只读分析：

```text
检查当前项目的异常处理路径。
先读取相关代码、配置和测试，只做分析，不修改文件。
给出根因、证据、风险和最小修复建议。
```

实施修复：

```text
修复订单重复提交问题。
先确认调用链、数据边界和当前基线，然后实施最小充分改动。
完成定向测试和必要回归，再按风险安排独立复审。
不要提交、推送、部署或重启。
```

明确交付边界：

```text
完成实现、测试和独立复审，并提交到本地 Git。
不要推送、部署或重启。
最终分别报告修改、验证、复审、提交、推送、部署、重启和生效状态。
```

包会根据技术栈自动选择最小充分 Skill，不会因为能力全部存在就同时加载所有 Skill。

## 3.1 V6.5 完整性 keyring 与事件封印

初始化只创建缺失 keyring，不覆盖现有密钥：

```powershell
python scripts\integrity-key.py init
python scripts\integrity-key.py status
python scripts\integrity-key.py verify
```

为当前 TaskOutcomeEvent V2 链头创建并验证封印：

```powershell
python scripts\event-seal.py create --event-file <task-outcome-v2.jsonl>
python scripts\event-seal.py verify --event-file <task-outcome-v2.jsonl>
```

事件密钥轮换：

```powershell
python scripts\integrity-key.py rotate --purpose event-hmac
```

旧密钥进入 `RETIRED` 并继续验证历史封印，新封印只使用 `ACTIVE` 密钥。状态 `SEALED_CURRENT` 表示当前链头已封印；`VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL` 表示历史封印有效、之后又出现合法事件，重新执行 `create` 即可覆盖当前链头。

宿主会话 JSONL 只用于实际模型旁证和冲突探测。即使字段关联完整，也不能升级为可信 Hook 模型事实。发行验证把两件事分开：真实生命周期证明 Reviewer 确实启动和结束；直接调用已安装 PreToolUse Hook 形成的模型门禁报告证明 Luna Low → Luna Medium → Terra Medium → Terra High 路线、Terra High 上限以及 Sol/xhigh 拒绝。两者都通过时发行门禁才通过。

## 3.2 Reviewer 校准

自观察快照中的 `reviewer_stats` 提供：

- 稳定 `result_id` 去重与冲突计数；
- 独立任务数、归因覆盖率和已标注 finding 数；
- adoption rate 与 Wilson 95% 区间；
- 单次耗时、单位采纳/修复成本与收益代理；
- `INSUFFICIENT_DATA / OBSERVE / EFFECTIVE / HIGH_DUPLICATION / LOW_YIELD_CANDIDATE / CONFLICT` 状态。

校准只形成观察和 Proposal 候选，不自动停用 Reviewer，不改变模型路由，也不产生执行授权。

## 4. 10 个 Skill

| Skill | 主要用途 |
|---|---|
| `java-backend-engineering` | Java、Spring、JVM、Maven、事务、并发、SSE |
| `python-backend-ai-engineering` | Python、FastAPI、Django、Flask、异步、Celery、AI/RAG/GPU Worker |
| `frontend-engineering` | JavaScript、TypeScript、React、Vue、Angular、Svelte、浏览器与 Renderer |
| `data-middleware-ai-infrastructure` | SQL、Redis、MQ、ES、存储、GPU、Docker、Kubernetes、网络 |
| `log-observability-analysis` | 日志、Metrics、Trace、Profiling、告警和变更事件 |
| `engineering-quality-delivery` | 修改、测试、Git、发布、回滚、审批和最终交付 |
| `multi-agent-independent-review` | 高风险实施前审查和行为改动后的独立复审 |
| `technical-document-writing` | 技术方案、架构、接口、部署、故障和正式报告 |
| `long-running-task-memory` | 跨会话、多阶段、多模块、多 Agent 和上下文压缩 |
| `controlled-evolution-governance` | 跨任务复盘、自观察、成本路由、Reviewer 收益和 Proposal 治理 |

显式指定 Skill：

```text
使用 $python-backend-ai-engineering 检查这个 FastAPI 服务的并发问题。
先分析，不修改。
```

每个阶段通常选择 1 个主领域 Skill，必要时组合质量、日志、复审、文档或长期任务 Skill。

## 5. 7 个 Reviewer

| Reviewer | 审查边界 |
|---|---|
| `cp_review_functional_business` | 功能正确性与业务口径 |
| `cp_review_compatibility_regression` | 旧接口、旧数据、回归与兼容 |
| `cp_review_security_access` | 认证、鉴权、越权、注入和敏感信息 |
| `cp_review_performance_resources` | SQL、I/O、连接、线程、队列和资源负担 |
| `cp_review_data_contract` | 数据库、API、Redis、MQ、序列化和一致性边界 |
| `cp_review_state_concurrency` | 竞态、幂等、超时、重试、取消和状态边界 |
| `cp_review_test_delivery` | 测试证据、失败项、文档和交付边界 |

自动选择示例：

```text
修复完成后，根据实际风险选择必要的独立 Reviewer 做逻辑只读复审。
不要为了形式全部启动。
```

显式选择示例：

```text
启动 cp_review_security_access，使用 Luna Low，
只检查鉴权、越权和敏感信息风险，不修改文件。
```

Reviewer TOML 不写死模型。自动成本路线：

```text
Luna Low -> Luna Medium -> Terra Medium -> Terra High
```

自动流程最高 `gpt-5.6-terra + high`。显式 Sol、Terra xhigh、max、ultra、未知模型或无法证明不超过上限的自动派发会被 PreToolUse Hook 拒绝。

## 6. 长期任务

跨会话、多阶段、多模块或多 Agent 任务可以明确启用长期任务记忆：

```text
这是一个长期任务。
使用 $long-running-task-memory 维护目标、计划、授权、证据、风险和检查点。
每完成一个可独立恢复阶段写一次检查点，持续到全部验收完成。
```

典型控制文件：

```text
CURRENT_TASK.md
PLAN.md
PROGRESS.md
```

恢复示例：

```text
恢复上次长期任务，读取当前任务、计划阶段和最近三个检查点，
再核对当前 Git、源码、配置和运行状态后继续。
```

检查点保存可验证事实、证据、授权、风险和下一步。检查点不会自动晋升为项目记忆或跨项目知识。

## 7. 生命周期记录

六个 Hook 对应以下事件：

```text
UserPromptSubmit -> TURN_OPENED
PreToolUse       -> PRE_TOOL_GUARD
SubagentStart    -> SUBAGENT_STARTED
SubagentStop     -> SUBAGENT_STOPPED
Stop             -> TASK_COMPLETED
SessionEnd       -> SESSION_ENDED
```

TaskOutcomeEvent 2.0 保存最小结构化元数据：

- event、session、turn、task 引用；
- `project_id + repo_fingerprint`；
- 明确宿主字段提供的实际模型和推理强度；
- Reviewer、发现、修复轮次等计数；
- 明确终态，缺少时为 `UNKNOWN`；
- 前向 SHA-256 链，可选 HMAC；
- 事实来源字段，区分宿主明确值与 unavailable。

V6.5 将事件写入连续 segment。跨段缺失、顺序错误、哈希损坏或 schema 非法时失败关闭。进程中断留下的活动尾部半记录会移动到带时间戳的审计文件，完整链继续保留。

默认不保存原始 Prompt、完整回答、代码正文、Diff、Patch、Token、Cookie、API Key 或凭据。安装前不存在的历史事件不会自动补写。

## 8. 跨项目隔离

每个项目同时绑定：

```text
project_id
repo_fingerprint
```

聚合、Snapshot、Assessment 和 Proposal 只有在两项同时匹配时才可使用。任一不一致都停止跨任务聚合，避免其他项目的表结构、接口、凭据、业务口径或观察结论进入当前项目。

## 9. 复盘与受控演进

复盘提示示例：

```text
使用 $controlled-evolution-governance，
分析当前项目近期的 Event、Checkpoint、Review 和 Evidence，
生成 Snapshot、Assessment 和 Optimization Proposal。
只生成提案，不接受、不实施。
```

标准链路：

```text
Lifecycle Event
  -> Task 聚合
  -> Snapshot
  -> Assessment
  -> Optimization Proposal
  -> 人工 ACCEPT / REJECT / DEFER
  -> ACCEPT 后另建实施任务
  -> 独立验证并关闭 Proposal
```

前置信息由生命周期 Hook 自动记录最小元数据；长期任务的目标、计划、授权、关键决策和验证证据由长期任务记忆在可恢复节点维护。没有记录或证据不足的部分必须标记 `UNKNOWN`、列出缺口或停止生成 Proposal，不能推测补全。

`execution_authorization=NONE` 永久成立。ACCEPT 只表示方向被认可，不授予文件修改、提交、推送、部署、重启或生产操作权限。

## 10. 安全与授权

以下动作始终作为独立边界：

- 只读分析；
- 本地文件修改；
- 测试或真实外部调用；
- Git commit；
- Git push；
- 部署；
- 重启；
- 数据修改；
- 生产操作。

测试通过只能证明测试范围内的行为，不会自动授予其他动作。最终报告必须分别说明已修改、静态检查、运行验证、独立复审、提交、推送、部署、重启和已生效状态。

## 11. 常见故障

### Plugin 文件存在但未启用

以 `codex plugin list --json` 为准。重新执行安装器和 `verify`，不要仅根据文件存在判断。

### Windows Hook 找不到 Python

V6.5 不依赖额外 `python3.exe`。确认可用的账户 CPython、`python.exe` 或 `py.exe -3` 至少存在一个，并检查 Hook 是否由 `cp_hook.cmd` 启动。

### 事件未进入聚合

检查 `project_id` 与 `repo_fingerprint` 是否同时匹配，再检查事件 segment 是否连续、哈希是否完整、schema 是否为 2.0。

### 复盘信息不足

使用现有 Git、日志、测试、检查点和 Evidence；缺口保持未验证。从后续长期任务开始启用长期任务记忆，不回填不存在的事实。

### 安装中断

```powershell
python scripts\package_manager.py status --scope user --mode plugin --json
python scripts\package_manager.py doctor --recover
```

不要递归删除整个 `.codex`、`.agents` 或 plugins 目录。检测到未知内容或归属冲突时保留日志并停止覆盖。

## 12. 验收清单

- [ ] Codex 为 0.150.1
- [ ] Plugin 为 installed=true、enabled=true、version=6.5.0
- [ ] 10 个 Skill 可发现
- [ ] 7 个 Reviewer 可发现且 TOML 未固定模型
- [ ] 6 个 Hook 可加载
- [ ] SessionEnd timeout 为 3 秒
- [ ] Windows Hook 不依赖额外 python3.exe
- [ ] 主 Agent 模型配置未变化
- [ ] 历史项目上下文和自观察数据未减少
- [ ] 升级备份保留
- [ ] 无活动安装事务
- [ ] 正式 ZIP 双构建字节一致
- [ ] ZIP、Marketplace、cache payload digest 一致
- [ ] 新会话产生完整五事件序列
- [ ] TaskOutcomeEvent schema 为 2.0 且哈希链连续
- [ ] `project_id + repo_fingerprint` 双重隔离通过
- [ ] 模型门禁允许 Terra High，拒绝 Terra xhigh、Sol 和更高自动档位
- [ ] 宿主会话模型仅标记 DIAGNOSTIC，未冒充 Hook 可信字段
- [ ] 统一验证器和 attestation 绑定全部正式证据

安装与恢复细节见 `docs/INSTALLATION_RECOVERY.md`，版本变化见 `docs/releases/v6.5.0/RELEASE_NOTES.md`。
