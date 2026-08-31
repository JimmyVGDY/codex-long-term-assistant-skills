> **V6.6 目标宿主：Windows 原生 Codex CLI 0.150.1。Plugin 成功状态以 `codex plugin list --json` 的 installed、enabled、version 三项读回为准。**

# Codex 跨项目长期技术助手 Skills 安装包 V6.6

**版本：6.6.0｜可信模型证据边界、多进程恢复、延迟封印与事件健康治理**

V6.6 在 V6.5 完整性闭环上增加可信宿主证明契约、Windows spawn 多进程故障测试、SessionEnd 预算外延迟封印、Reviewer 校准 V2、非破坏事件归档、容量预算和跨项目健康概览。Codex 0.150.1 仍只提供诊断旁证，实际运行模型证据保持 `UNAVAILABLE`。10 个 Skill、7 个 Reviewer、6 个 Hook、TaskOutcomeEvent 2.0、项目双重隔离和 Terra High 自动上限保持兼容。

## 核心能力

- 10 个工程 Skill：Java、Python/AI、前端、数据与基础设施、日志、质量交付、独立复审、技术文档、长期任务记忆、受控演进治理。
- 7 个逻辑只读 Reviewer：按风险选择，累计预算受控，自动模型最高 `gpt-5.6-terra + high`。
- Plugin-first：提供账户级 Plugin、standalone 和仓库级 Skill 三种安装形态。
- 确定性生命周期：覆盖 `UserPromptSubmit / PreToolUse / SubagentStart / SubagentStop / Stop / SessionEnd`。
- TaskOutcomeEvent V2：严格 schema、最小元数据、前向 SHA-256 链、可选 legacy HMAC。
- 完整性 keyring：Windows DPAPI 或 POSIX 0600 存储，`event-hmac` 与 `release-attestation` 独立轮换。
- Detached seal：对当前事件链头形成可轮换 HMAC 封印；旧写入形成未封印尾部，不破坏历史封印。
- Reviewer Calibration：按 `result_id` 去重，输出 Wilson 95% 区间、样本充分性、重复冲突和收益状态。
- Reviewer Calibration V2：增加任务难度、根因簇重复、采纳原因和带证据的回归预防收益。
- 延迟自动封印：SessionEnd 只签名入列并立即返回；独立 worker 追加结束事件、封印和幂等确认。
- 事件健康治理：非破坏归档已关闭 segment，提供容量预算和不含敏感正文的跨项目概览。
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

在解压后的 V6.6 根目录执行：

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
version   = 6.6.0
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

默认只记录最小结构化元数据，不保存原始 Prompt、完整回答、代码正文、Diff、Token、Cookie、API Key 或凭据。缺少明确终态时记录 `UNKNOWN`；显式但非法的终态直接拒绝。Hook 实际模型与推理强度只有在宿主提供外部信任锚可验证、带有效期且绑定 session/turn/agent 的证明时才标为 `VERIFIED`。Codex 0.150.1 的 `session_meta + turn_context` 只作诊断旁证，不会回填 Hook 实际字段。

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

## 完整性封印

```powershell
python scripts\integrity-key.py init
python scripts\event-seal.py create --event-file <task-outcome-v2.jsonl>
python scripts\event-seal.py verify --event-file <task-outcome-v2.jsonl>
python scripts\integrity-key.py rotate --purpose event-hmac
python scripts\seal-worker.py --queue <project-context>\<project-id>\feedback\seal-queue
python scripts\event-archive.py health --project-context-root <project-context>
```

DPAPI keyring 绑定 Windows 当前账户与主机，WSL/POSIX 不会静默解密或替代。原始 SHA-256 事件链仍可跨环境验证；跨 issuer 的 HMAC 历史需要分别保留对应 keyring。

## 发行验证

```powershell
python scripts\validate-package.py
python scripts\build-release.py reproducible --output Codex-Skills-V6.6.zip --witness deterministic-build-v6.6.json
python scripts\build-release.py verify --archive Codex-Skills-V6.6.zip
```

统一验证器用于绑定正式 ZIP、包内校验、确定性构建见证、Codex 0.150.1、Plugin 精确状态、真实生命周期、已安装 PreToolUse 模型门禁报告和三段 payload 身份。Codex 0.150.1 未提供 Hook 实际模型字段时，宿主会话只保留诊断旁证，不作为发行通过条件：

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

详细操作见 `docs/USER_GUIDE_V6.6.md`，恢复规则见 `docs/INSTALLATION_RECOVERY.md`，版本变化见 `RELEASE_NOTES_V6.6.md`。
