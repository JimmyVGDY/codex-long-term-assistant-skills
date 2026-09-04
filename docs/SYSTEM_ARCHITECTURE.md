# V7.4 当前系统架构与安全边界

> 状态：`active`。本页描述 V7.4.3 当前包的整体架构；旧版本设计与发行证据只用于历史追溯。

## 1. 分层

```text
Global AGENTS（最小跨项目规则）
        ↓
10 Skills（4 个主领域 + 6 个支撑能力，按需加载）
        ↓
Main Agent / 7 Reviewers
        ↓
6 Lifecycle Hooks
        ↓
TaskOutcomeEvent V3
        ↓
Project Context Runtime
        ↓
Observation / Assessment / Proposal
        ↓
Human Decision + Independent Implementation Task
```

包版本是 V7.4.3；`TaskOutcomeEvent V3`、Evolution Policy 等名称是组件合同或数据格式标识，不代表安装了旧版软件。

## 2. Skill 路由

每个阶段只选择一个主领域 Skill：

- `backend-engineering`：服务端应用、API、业务逻辑、事务、并发与 Worker；
- `frontend-engineering`：浏览器、WebView、Renderer、状态与交互；
- `ai-engineering`：模型调用、RAG、Agent、评测、推理与多模态生成；
- `data-middleware-infrastructure`：数据库、缓存、MQ、搜索、存储、GPU、容器与网络。

日志、质量交付、独立复审、技术文档、长期记忆和受控演进作为支撑能力按阶段加载。详细边界见 [V7.4 领域 Skill 架构](V7_DOMAIN_SKILL_ARCHITECTURE.md) 和 [V7.4 Skill 触发矩阵](SKILL_TRIGGER_MATRIX.md)。

## 3. 项目与数据隔离

每条 TaskOutcomeEvent V3 至少绑定：

- `project_id`；
- `repo_fingerprint`；
- `session_id / turn_id / task_id`；
- `event_id`。

观察流程先验证哈希链或 HMAC，再检查 `project_id + repo_fingerprint`，随后按 `event_id` 去重并按 Task 聚合。项目或仓库身份不一致时失败关闭，不把跨项目记录纳入同一结论。

## 4. Hook 与模型边界

`PreToolUse` 对自动子 Agent 的模型上限做前置检查；`SubagentStart` 和 `SubagentStop` 记录最小运行事实，其余 Hook 形成生命周期事件。Hook Guard 是工作流保护，不是平台级不可绕过安全边界。

系统只验证派发前的批准档位、permit 和预算预占。宿主实际模型身份与推理强度不读取、不推断，也不进入生命周期、Reviewer、演进或发布证明。

## 5. Reviewer 隔离

Reviewer TOML 中的 `read-only` 只表示配置意图。父会话可写且没有有效系统拒绝证据时，复审只能标记为 `logical-readonly`；只有父会话整体只读或隔离探针确实被系统拒绝时，才能标记为 `system-readonly`。自查不能冒充独立 Reviewer。

## 6. 隐私与完整性

生命周期数据只保留治理所需的最小结构化元数据。疑似 Prompt、完整回答、代码正文、Patch、Diff、Token、Secret、Authorization、Cookie、API Key 和 Private Key 默认不得持久化。

事件链采用前向 SHA-256 完整性校验，可按配置增加 HMAC 和 detached seal。SessionEnd Hook 只构造有上限且不含正文的净化事件并无等待派发，不执行事件链 I/O 或同步管道写入；detached worker 统一校验稳定生命周期身份，完成语义去重、持久化，并使用绑定 `event_id` 的 v2 签名任务封印事件链。带 `seal_required` 的未封印尾部不得进入 Evolution。活动事件、只读分段和归档清单继续保持项目身份与链头连续性；损坏、串线或引用不一致时失败关闭。

## 7. Proposal 权限模型

Proposal 只是一条治理建议：

```text
PENDING_REVIEW
  ├─ REJECTED
  ├─ DEFERRED
  └─ ACCEPTED
       ↓
IMPLEMENTATION_LINKED
       ↓
VALIDATION_RECORDED
       ↓
CLOSED
```

被新证据取代的提案可以标记为 `SUPERSEDED`。任何状态都不会把 `execution_authorization` 从 `NONE` 改成其他值；人工接受后仍需建立新的实施任务并重新取得修改、提交、推送或发布授权。

## 8. 当前与历史文档边界

- 当前规范从[文档中心](README.md)进入，并明确标记 V7.4；
- 升级来源版本、迁移映射和组件合同版本可以在当前文档中出现，但必须说明其用途；
- 历版发行说明、验证报告和设计文档保留用于追溯，不作为当前安装、运行或验收结论；
- 历史详情页不进入默认站内搜索，避免旧命令与当前操作说明混淆。
