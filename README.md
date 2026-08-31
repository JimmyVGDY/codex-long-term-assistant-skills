> **V6.4 目标宿主：Windows 原生 Codex CLI 0.150.1。Plugin 成功状态以 `codex plugin list --json` 的 installed、enabled、version 三项读回为准。**

# Codex 跨项目长期技术助手 Skills 安装包 V6.4

**版本：6.4.0｜端到端载荷身份与可恢复证据链**

V6.4 在 V6.3 可恢复事务与可证明发行基线上，补齐 ZIP、Marketplace、Plugin cache 的同源身份校验，增加事件安全分段、半记录恢复、旧状态迁移、Codex 能力探测和统一发行验证器。10 个 Skill、7 个 Reviewer、6 个 Hook、TaskOutcomeEvent 2.0、项目双重隔离和 Terra High 自动上限保持兼容。

## 核心能力

- 10 个工程 Skill：Java、Python/AI、前端、数据与基础设施、日志、质量交付、独立复审、技术文档、长期任务记忆、受控演进治理。
- 7 个逻辑只读 Reviewer：按风险选择，累计预算受控，自动模型最高 `gpt-5.6-terra + high`。
- Plugin-first：提供账户级 Plugin、standalone 和仓库级 Skill 三种安装形态。
- 确定性生命周期：覆盖 `UserPromptSubmit / PreToolUse / SubagentStart / SubagentStop / Stop / SessionEnd`。
- TaskOutcomeEvent V2：严格 schema、最小元数据、前向 SHA-256 链、可选 HMAC。
- 事件安全分段：跨段连续校验，活动尾部半记录审计隔离，进程崩溃后确定性恢复。
- 双重项目隔离：`project_id + repo_fingerprint` 任一不匹配均拒绝聚合。
- 可恢复安装事务：Marketplace 子树、manifest、Plugin cache、注册状态和 state schema 迁移均纳入 journal。
- 端到端载荷身份：正式 ZIP、Marketplace、Plugin cache 共享规范化 payload digest。
- 受控 Proposal：`execution_authorization=NONE` 永久成立；决定与实施授权保持分离。

## 账户级目录

- Skill：`$HOME/.agents/skills`
- Reviewer：`${CODEX_HOME:-$HOME/.codex}/agents`
- 全局规则：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- Plugin Marketplace：`$HOME/.agents/plugins/cp-assistant-marketplace`
- 项目上下文：`${CODEX_HOME:-$HOME/.codex}/project-context/<project-id>`

Windows 原生进程若继承 `/mnt/c/.../.codex`，安装器会转换为盘符路径；WSL 风格路径不会直接作为 Windows 安装目标。

## 推荐升级流程

在解压后的 V6.4 根目录执行：

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

只有 Plugin 读回同时满足以下条件，才可判定账户级升级成功：

```text
installed = true
enabled   = true
version   = 6.4.0
```

`verify` 还会校验 10 个 Skill、7 个 Reviewer、6 个 Hook、载荷 digest、Marketplace/cache 身份及状态文件。文件复制完成不等同于 Plugin 注册成功。

## 其他安装形态

Standalone：

```powershell
python scripts\package_manager.py install --scope user --mode standalone --dry-run
python scripts\package_manager.py install --scope user --mode standalone
python scripts\package_manager.py verify --scope user --mode standalone
```

仓库级 Skill：

```powershell
python scripts\package_manager.py install --scope repo --repo-path <repository> --dry-run
python scripts\package_manager.py install --scope repo --repo-path <repository>
python scripts\package_manager.py verify --scope repo --repo-path <repository>
```

仓库级形态不改动账户级 Reviewer、Hook、全局规则或 Plugin 注册。

## 崩溃恢复

检测到活动事务时，先读取状态，再执行恢复：

```powershell
python scripts\package_manager.py status --scope user --mode plugin --json
python scripts\package_manager.py doctor --recover
```

恢复仅处理 journal 中已声明且归属本包的受管目标。未知文件、外部漂移、路径越界、符号链接、Junction、Reparse Point、未知 state schema 或不完整备份均失败关闭。不得通过删除整个 `.codex`、`.agents` 或 plugins 目录处理故障。

## 自观察与复盘

```text
Lifecycle Hook
  -> TaskOutcomeEvent V2
  -> event_id 去重
  -> Task 聚合
  -> project_id + repo_fingerprint 隔离
  -> Snapshot
  -> Assessment
  -> Proposal
  -> 人工决策
  -> 独立实施任务
```

默认只记录最小结构化元数据，不保存原始 Prompt、完整回答、代码正文、Diff、Token、Cookie、API Key 或凭据。缺少明确终态时记录 `UNKNOWN`；显式但非法的终态直接拒绝。Hook 事件中的宿主实际模型与推理强度只接受明确字段，不从通用别名推断；生命周期验收可另行关联 Codex 子任务会话中的 `session_meta + turn_context`，但不会把该证据回填成 Hook 实际字段。

## 发行验证

```powershell
python scripts\validate-package.py
python scripts\build-release.py reproducible --output Codex-Skills-V6.4.zip --witness deterministic-build-v6.4.json
python scripts\build-release.py verify --archive Codex-Skills-V6.4.zip
```

统一验证器用于绑定正式 ZIP、包内校验、确定性构建见证、Codex 0.150.1、Plugin 精确状态、生命周期证据和三段 payload 身份：

```powershell
python scripts\verify-release.py --help
```

没有实际宿主证据的状态必须保持 `NOT_EXECUTED` 或未验证，不得写成 PASS。

## 安全边界

- 不改写 `config.toml` 或主 Agent 模型配置；
- Reviewer TOML 不固定模型；
- 自动路线为 Luna Low → Luna Medium → Terra Medium → Terra High；
- 自动流程最高 Terra High；
- 不自动修改 Skill、Reviewer、路由、全局规则或业务仓库；
- 不自动接受或实施 Proposal；
- 不自动提交、推送、部署、重启或操作生产环境；
- Event、Snapshot、Assessment、Proposal、项目上下文和升级备份不会随普通升级或卸载自动删除。

详细操作见 `docs/USER_GUIDE_V6.4.md`，恢复规则见 `docs/INSTALLATION_RECOVERY.md`，版本变化见 `RELEASE_NOTES_V6.4.md`。
