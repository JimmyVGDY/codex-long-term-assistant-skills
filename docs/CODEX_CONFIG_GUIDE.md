<!-- Generated compatibility copy from docs/operations/CODEX_CONFIG_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

[当前入口](operations/CODEX_CONFIG_GUIDE.md)

# Codex 配置指南

> 状态：`active`。本页说明当前包配置；安装、升级和恢复步骤以[安装与恢复](operations/INSTALLATION_RECOVERY.md)为准。

## 1. 配置边界

- 主 Agent 继续使用请求方在 Codex 中选择的模型，本包不覆盖主模型；
- 未显式指定的子 Agent 可以使用宿主默认值；
- 本包自动派发只允许 Luna Low、Luna Medium、Terra Medium 和 Terra High；
- Reviewer TOML 不写死模型或推理强度，由受控调度策略按任务选择；
- 精确模型配置只在宿主派发适配器中短暂用于请求校验，不进入本包的持久状态或治理结论。

## 2. 配置文件位置

### Windows PowerShell

```powershell
$env:USERPROFILE + "\.codex\config.toml"
```

### WSL、Linux 与 macOS

```bash
${CODEX_HOME:-$HOME/.codex}/config.toml
```

Windows 和 WSL 可能使用不同账户目录。原生 Windows Codex 的 `CODEX_HOME` 必须解析为原生 Windows 路径，不能把 `/mnt/c/...` 字面值当作安装目标。

## 3. 修改前备份

PowerShell：

```powershell
$path = "$env:USERPROFILE\.codex\config.toml"
Copy-Item -LiteralPath $path -Destination "$path.bak-$(Get-Date -Format yyyyMMdd-HHmmss)" -ErrorAction SilentlyContinue
```

Bash：

```bash
path="${CODEX_HOME:-$HOME/.codex}/config.toml"
[ -f "$path" ] && cp "$path" "$path.bak-$(date +%Y%m%d-%H%M%S)"
```

## 4. 子 Agent 默认配置

配置文件中只能保留一个 `[agents]` 表。已有该表时合并字段，不要追加第二个同名表。

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

这些值是宿主默认值，不会阻止显式派发选择其他允许档位。不要为了减少少量上下文而关闭中断消息；保留宿主默认行为有利于恢复和审计。

## 5. Reviewer 配置

以下受管 Reviewer 文件应保持动态模型选择：

```text
${CODEX_HOME:-$HOME/.codex}/agents/cp-review-*.toml
```

不要统一加入：

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
```

写死模型会覆盖受控调度和 `[agents]` 默认值，破坏 Luna 到 Terra High 的逐级路由。

## 6. Plugin 与 Hook

V7.8.1 使用冻结注册表适配 Codex CLI 0.154.0 与此前十个稳定发行版的 Plugin、Marketplace 及 PreToolUse/PostToolUse 接口。只有 `codex plugin list --json` 精确读回 `installed=true`、`enabled=true` 和 `version=7.8.1`，且 schema 3 宿主快照为 `HOST_COMPATIBLE`，才能确认 Plugin 注册成功；文件已复制到磁盘不等于已安装或已启用。

Plugin 通过 `hooks/hooks.json` 提供七个注册 Hook 入口。Windows 入口 `hooks\cp_hook.cmd` 会选择可用的 Python 启动器，不需要额外创建 `python3.exe` 垫片。SessionEnd 的宿主预算保持三秒：Hook 只构造有上限且不含正文的净化 Event V3，并以命令参数无等待派发 detached worker；不再扫描或写入事件链，也不再同步写管道。Worker 在 Hook 预算外完成稳定生命周期身份校验、语义去重、终态持久化、签名入队和封印。所有入口都会拒绝缺失稳定生命周期 ID 的事件，带 `seal_required` 的未封印链不得进入 Evolution。

## 7. 自动模型上限

```text
gpt-5.6-luna / low
gpt-5.6-luna / medium
gpt-5.6-terra / medium
gpt-5.6-terra / high
```

自动流程对显式 Sol、`xhigh`、`max`、`ultra`、未知模型和超过 Terra High 的配置失败关闭。未显式指定自动模型时使用 Task Envelope 的默认批准档位计费；派发后不读取或推断宿主实际模型信息。

## 8. 重新加载与验证

配置或 Reviewer 文件变化后，完全关闭并重新打开 Codex App、CLI 会话或 IDE 扩展，再检查：

1. `/model` 仍显示请求方选择的主模型；
2. `codex plugin list --json` 读回目标 Plugin 的安装、启用和版本；
3. 新任务能够发现十个当前 Skill 和七个 Reviewer；
4. 小型只读复审没有无理由启动大量 Reviewer；
5. 复审结果只记录批准派发档位、permit 引用、预留单位、结果指标与隔离等级。

完整安装、`doctor`、dry-run、verify 和恢复流程见[安装与恢复](operations/INSTALLATION_RECOVERY.md)。

## 可选项目门禁与实际加载

注册配置包含八个入口，项目门禁默认关闭。V7.8.1 中 `UserPromptSubmit` 是异步观察，`Stop` 是中性观察，`Interrupt` 由宿主控制；规范 `apply_patch` 仅在显式启用策略下由 PreToolUse/PostToolUse 推进 Operation v2，未配置或停用策略保持中性。

```text
未配置或 disabled ───────────────→ 原生写入保持宿主既有行为
旧策略 enabled + 原生写工具 ───→ 拒绝 LEGACY_WRITE_ORIGIN_UNAVAILABLE
UserPromptSubmit / Stop / Interrupt → 不消费旧 GateTask 控制状态
```

配置 `enabled=true`、Plugin 已加载和业务语义适用是不同结论。V7.8.1 只接受 Hook 建立的 Operation v2 起点、不同 B 的许可领取与匹配 PostTool 回执；旧 GateTask 回执不能授权原生写入。已打开会话可能仍使用旧 Plugin 快照，升级后应在新任务中读回实际行为。shell/MCP 等入口不能保证写前拦截。

冻结窗口内 11 个 Codex CLI 版本具有逐版本官方 UserPromptSubmit async 源码证据；真实 Desktop 与其他宿主仍需各自读回。旧门禁启用与停用入口见[能力索引与流程入口](CAPABILITY_INDEX.md)，但本补丁不把旧任务生命周期恢复为写入授权。
