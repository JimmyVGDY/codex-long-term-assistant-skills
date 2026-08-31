> **V6.3 已验证宿主：Codex CLI 0.150.1。Plugin 安装必须以 `codex plugin list --json` 的 installed+enabled+version 读回为成功标准。**

# Codex 跨项目长期技术助手 Skills 安装包 V6.3

**版本：6.3.0｜可恢复事务与可证明发行版**

V6.3 基于 V6.2 Windows 实机兼容基线，增加持久化安装事务、崩溃恢复、并发互斥、机器可读发行证明、真实生命周期验收、观测完整率、Reviewer 收益归因和字节级确定性 ZIP；项目身份、Task Envelope、Approval/Evidence、模型上限与受控 Proposal 边界保持不变。

## 核心能力

- **10 个工程 Skills**：Java、Python/AI、前端、数据/中间件/AI 基础设施、日志可观测性、质量交付、多 Agent 复审、技术文档、长期任务记忆、受控演进治理。
- **7 个专业 Reviewer**：职责隔离，自动模型最高 `gpt-5.6-terra + high`。
- **Plugin-first**：包含 `.codex-plugin/plugin.json`、`skills/`、`hooks/hooks.json`；同时提供 standalone 和 repo 安装方式。
- **确定性生命周期观测**：`UserPromptSubmit / PreToolUse / SubagentStart / SubagentStop / Stop / SessionEnd`。
- **TaskOutcomeEvent V2**：严格字段、非负计数、隐私最小化、SHA-256 链，可选 HMAC。
- **Task 级聚合**：先按 `event_id` 去重，再按 `task_id` 聚合，避免生命周期事件重复加权。
- **双重项目隔离**：`project_id + repo_fingerprint` 任一不匹配都拒绝聚合。
- **不可覆盖 Snapshot**：唯一 ID + `source_digest` + exclusive-create。
- **受控 Proposal 生命周期**：人工决定后仍需独立实施 Task、Git Baseline、Commit 和验证 Evidence；`execution_authorization` 永远为 `NONE`。
- **可恢复安装事务**：首个写入前持久化 Journal，全流程互斥、故障恢复、回滚失败可见、旧状态兼容。
- **可证明发行**：两次干净构建必须字节一致；外部 Attestation 绑定正式 ZIP、实机 Plugin 读回和真实生命周期证据。
- **观测质量门禁**：生命周期完整率、SessionEnd 覆盖率、终态覆盖率和 Reviewer 归因完整率不足时只形成 Snapshot。

## 目录约定

- 账户级 Skills：`$HOME/.agents/skills`
- 仓库级 Skills：`$REPO_ROOT/.agents/skills`
- 自定义 Reviewer：`${CODEX_HOME:-$HOME/.codex}/agents`
- 全局规则：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- 项目上下文：`${CODEX_HOME:-$HOME/.codex}/project-context/<project-id>`

V6 不再把 `$HOME/.agents/skills` 当成旧目录，也不会自动清理该目录中的未知 Skill。

## 安装前检查

```bash
python scripts/package_manager.py doctor
python scripts/package_manager.py status --scope user --mode plugin --json
```

### A. Plugin 模式（推荐）

先查看变更：

```bash
python scripts/package_manager.py install --scope user --mode plugin --dry-run
```

准备本地 Plugin Marketplace、Reviewer 和全局规则：

```bash
python scripts/package_manager.py install --scope user --mode plugin
```

安装器直接执行 Marketplace 与 Plugin 注册，并在提交事务前读回宿主状态。若检测到未完成事务，先执行 `python scripts/package_manager.py doctor --recover`。

### B. Standalone 模式

```bash
python scripts/package_manager.py install --scope user --mode standalone --dry-run
python scripts/package_manager.py install --scope user --mode standalone
python scripts/package_manager.py verify  --scope user --mode standalone
```

Standalone 会把账户 Skills 安装到 `$HOME/.agents/skills`，Reviewer/Runtime/Hooks 安装到 `CODEX_HOME` 对应目录，并合并本包受管 Hook，不覆盖其他 Hook 条目。

### C. 仓库级 Skills

```bash
python scripts/package_manager.py install --scope repo --repo-path /path/to/repository --dry-run
python scripts/package_manager.py install --scope repo --repo-path /path/to/repository
python scripts/package_manager.py verify  --scope repo --repo-path /path/to/repository
```

Repo 模式只安装当前仓库 `.agents/skills`，不修改账户级 Reviewer、Hooks 或全局 AGENTS。

## 卸载

```bash
python scripts/package_manager.py uninstall --scope user --mode standalone
```

或：

```bash
python scripts/package_manager.py uninstall --scope user --mode plugin
```

检测到受管资源被外部修改时默认拒绝覆盖式卸载；确认后才使用 `--force`。项目上下文和观察数据不会随卸载自动删除。

## 确定性自观察

V6 的普通任务只写最小生命周期元数据，完整 Evolution 分析仍然按需运行：

```text
Hooks
  ↓
TaskOutcomeEvent V2
  ↓ event_id 去重
Task Aggregate
  ↓ project_id + repo_fingerprint
Observation Snapshot
  ↓
Assessment
  ↓
Optimization Proposal
  ↓
Human Decision
```

没有明确终态时记录 `UNKNOWN`，不会把 Stop 自动判定为成功，也不会从通用 `status` 推断失败。

## Proposal 实施闭环

```bash
python scripts/evolution.py decide ... --decision accept
python scripts/evolution.py link-implementation ... --task-id TASK-... --git-baseline <baseline>
python scripts/evolution.py record-validation ... --commit <commit> --evidence <evidence-ref>
python scripts/evolution.py close ... --final-outcome PASS
```

`ACCEPT` 只认可优化方向，不授予文件修改、提交、推送、部署或生产操作权限。

## 验证

```bash
python scripts/validate-package.py
python scripts/build-release.py reproducible --output Codex-Skills-V6.3.zip --witness deterministic-build-v6.3.json
```

V6 发布验证明确区分：

- 本地语法/结构/单元和回归测试：可自动验证；
- 35 条路由用例定义是否合法：可自动验证；
- 真实 Codex 隐式 Skill 激活率、不同宿主 Plugin/Hooks 端到端、Windows PowerShell 实机：没有实际环境证据时必须标记 `NOT_EXECUTED`。

详见 `RELEASE_NOTES_V6.3.md`、`docs/USER_GUIDE_V6.3.md` 和 `docs/V6_ARCHITECTURE.md`。
