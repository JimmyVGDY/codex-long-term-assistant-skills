# V6 架构与安全边界

## 1. 分层

```text
Global AGENTS（最小跨项目规则）
        ↓
10 Skills（渐进加载）
        ↓
Main Agent / 7 Reviewers
        ↓
Lifecycle Hooks
        ↓
TaskOutcomeEvent V2
        ↓
Project Context Runtime
        ↓
Observation / Assessment / Proposal
        ↓
Human Decision + Independent Implementation Task
```

## 2. 数据隔离

每条 V2 事件至少绑定：

- `project_id`
- `repo_fingerprint`
- `session_id / turn_id / task_id`
- `event_id`

观察时：先验证 Hash Chain/HMAC，再校验项目/仓库，再去重，再 Task 聚合。任何跨项目/跨仓库记录都不能“忽略后继续形成同一结论”，而是失败关闭当前观察。

## 3. Hook 权限

PreToolUse 对自动子 Agent 模型上限做前置 Guard；其他 Hook 的观测失败默认不阻塞普通开发。Hook Guard 仍不是平台级不可绕过安全边界，因此 SubagentStart 的实际运行数据是第二层检测证据。

## 4. 隐私

生命周期日志只保留治理所需元数据。疑似 Prompt、Content、Message、Response、Patch、Diff、Code、Token、Secret、Authorization、Cookie、API Key、Private Key 字段默认脱敏。

## 5. Proposal 权限模型

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

被新提案取代时可 `SUPERSEDED`。任何状态都不会把 `execution_authorization` 从 `NONE` 改成其他值。
