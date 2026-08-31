# V6.3 安装、验证与事务恢复

## 适用范围

- 目标宿主：Windows 原生 Codex CLI 0.150.1。
- 推荐形态：账户级 Plugin 模式。
- 升级基线：V6.1.0 或 V6.2.0。
- 受管目录：账户 Skill、Reviewer、全局规则、Plugin Marketplace 与 Plugin 注册状态。

安装器不改写 `config.toml`，不删除项目上下文、Event、Snapshot、Assessment、Proposal 或历史备份。

## 账户级目录

- Skill：`$HOME/.agents/skills`
- Reviewer：`${CODEX_HOME:-$HOME/.codex}/agents`
- Global：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- Plugin Marketplace：`$HOME/.agents/plugins/cp-assistant-marketplace`
- 安装状态：`${CODEX_HOME:-$HOME/.codex}/cp-assistant-v6-state.json`
- 安装锁与活动事务：位于 `CODEX_HOME`，只覆盖本包的安装操作。

Windows 原生进程若继承 `/mnt/c/Users/.../.codex`，必须先转换为盘符路径。安装目标不得保留 WSL 风格路径。

## 标准升级流程

在解压后的 V6.3 根目录执行：

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

完成条件为 Plugin `installed=true`、`enabled=true`、`version=6.3.0`，同时 10 个 Skill、7 个 Reviewer 和 6 个 Hook 均通过安装校验。仅复制文件不构成 Plugin 安装成功。

## 持久化事务

安装与卸载在首次受管写入前建立事务日志和互斥锁。事务记录旧状态、备份、计划动作、已完成动作和 Plugin 注册阶段；成功提交后归档事务并移除活动日志。

以下情况按失败关闭处理：

- 存在未完成活动事务；
- Codex 版本或 Plugin 命令能力不兼容；
- 目标或祖先目录为 Junction、Reparse Point 或符号链接；
- 受管文件发生未解释漂移；
- 备份、状态或事务完整性校验失败；
- 回滚不能恢复文件或 Plugin 注册状态。

同一 `CODEX_HOME` 同时只允许一个本包安装事务。锁冲突输出持有进程与事务位置，不进行并发写入。

## 崩溃后检查与恢复

先读取状态，不直接重复安装：

```powershell
python scripts\package_manager.py status --scope user
python scripts\package_manager.py doctor
```

存在未提交事务时执行：

```powershell
python scripts\package_manager.py recover --scope user
```

恢复只处理日志中已记录且归属本包的动作：

- `PREPARED` 且尚未发生写入时，清理空事务；
- 已发生文件写入时，按备份恢复受管文件；
- 已发生 Plugin 注册变更时，恢复原 Plugin 版本与启用状态；
- 合并型 `AGENTS.md` 与 standalone `hooks.json` 只撤销本包标记区块；
- 遇到未知内容或归属冲突时停止并保留证据，不覆盖外部修改。

恢复完成后重新执行 `doctor`、dry-run、正式安装和 `verify`。不得手工删除整个 `.codex`、`.agents` 或 plugins 目录。

## 回滚与卸载

先查看计划：

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin --dry-run
```

正式卸载：

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin
```

卸载按安装状态和内容哈希识别受管资产，并恢复升级前备份。外部漂移默认阻断；`--force` 仅适用于已确认的受管漂移，不授权删除未知资产。

## 发行包证明

确定性构建：

```powershell
python scripts\build-release.py reproducible `
  --output ..\Codex-Skills-V6.3.zip `
  --witness ..\deterministic-build-v6.3.json
```

机器证明由正式 ZIP 哈希、Codex 版本证据、Plugin 状态、生命周期报告、包校验与确定性构建见证共同构成。验证命令：

```powershell
python scripts\release-attestation.py verify `
  --attestation ..\release-attestation-v6.3.json `
  --artifact ..\Codex-Skills-V6.3.zip
```

机器证明只保存白名单摘要与证据哈希，不保存原始 Prompt、完整回答、代码正文、凭据或原始会话标识。
