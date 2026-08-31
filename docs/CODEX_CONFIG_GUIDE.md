# Codex 子 Agent 成本配置指南

## 一、配置目标

- 主 Agent 继续由你在 Codex 中选择 Terra 或其他模型；
- 未显式指定的子 Agent 默认使用 Luna Medium；
- 本 Skill 根据任务把少量子 Agent 升到 Terra Medium 或 Terra High；
- 默认同时最多 3 个子 Agent；
- 自动工作流最高不超过 Terra High。

## 二、找到配置文件

### Windows PowerShell

```powershell
$env:USERPROFILE + "\.codex\config.toml"
```

通常是：

```text
C:\Users\你的用户名\.codex\config.toml
```

### WSL / Linux / macOS

```bash
${CODEX_HOME:-$HOME/.codex}/config.toml
```

通常是：

```text
~/.codex/config.toml
```

Codex 在 Windows 和 WSL 中运行时可能读取不同的用户目录。在哪个环境启动 Codex，就修改那个环境对应的配置文件。

## 三、先备份

### PowerShell

```powershell
$path = "$env:USERPROFILE\.codex\config.toml"
Copy-Item $path "$path.bak-$(Get-Date -Format yyyyMMdd-HHmmss)" -ErrorAction SilentlyContinue
```

### Bash

```bash
path="${CODEX_HOME:-$HOME/.codex}/config.toml"
[ -f "$path" ] && cp "$path" "$path.bak-$(date +%Y%m%d-%H%M%S)"
```

## 四、合并 `[agents]` 配置

配置文件中只能保留一个 `[agents]` 表。已有 `[agents]` 时修改其中字段，不要再追加第二个同名表。

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

字段含义：

- `enabled`：启用多 Agent；
- `max_concurrent_threads_per_session`：限制并发子线程，不包含主 Agent；
- `default_subagent_model`：未显式指定时使用 Luna；
- `default_subagent_reasoning_effort`：未显式指定时使用 Medium。

不建议为了节省极少量上下文而设置 `interrupt_message = false`。保留默认值 `true`，可让子 Agent 在模型上下文中感知任务被中断，有利于后续恢复和审计。

## 五、不要在 Reviewer TOML 中写死模型

保留以下文件中的动态行为：

```text
~/.codex/agents/cp-review-*.toml
```

不要统一加入：

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
```

Agent 文件一旦写死模型或强度，会优先于 spawn 和 `[agents]` 默认值，导致 Luna 降级与四级路由失效。

## 六、安装或更新本包

在解压后的安装包根目录执行：

### PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-user.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify-user-install.ps1
```

### Bash

```bash
bash ./scripts/install-user.sh
bash ./scripts/verify-user-install.sh
```

安装脚本会更新受管的 `AGENTS.md`、Skills 和自定义 Reviewer，但不会自动修改你的 `config.toml`。

## 七、重启 Codex

完全关闭并重新打开 Codex App、CLI 会话或 IDE 扩展。Skill 文件通常会自动检测，但全局配置和 Agent 文件建议重启后验证。

## 八、验证配置

1. 主会话通过 `/model` 确认仍使用你选择的主模型，例如 Terra Medium。
2. 让 Codex执行一个明确的小型只读任务，并要求使用一个 Luna Reviewer。
3. 查看子 Agent 线程或活动面板，确认没有无理由启动大量 Reviewer。
4. 使用复审控制器的 `status` 查看请求档位分布。

示例：

```bash
python3 ~/.codex/skills/multi-agent-independent-review/scripts/review_controller.py status \
  --review-dir /path/to/external-memory/reviews/FB-001
```

状态中应看到类似：

```text
模型档位分布: {"luna-medium": 1, "terra-medium": 1}
Terra High Reviewer: 0 / 1
```

## 九、配置边界

`[agents]` 中的模型和强度是默认值，显式 spawn 可以覆盖。V4.2 通过 Skill 规则和 `review_controller.py` 限制本工作流的自动派发，但它不是 Codex 平台级模型 allowlist；用户手工绕过控制器启动更高模型时，包无法从底层阻止，只能在流程审计中识别和报告。
