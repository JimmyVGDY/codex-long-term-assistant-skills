# V6.2 Windows 实机兼容固化版

V6.2 基于 V6.1，并将 Windows 原生 Codex CLI 0.150.1 实机升级与生命周期验收中发现、修复并验证的兼容问题正式纳入发行包。V6.2 不是仅修改版本号的重新打包。

## 主要变化

- 六个 Windows Hook 统一通过 quote-free `cmd.exe /d /c %PLUGIN_ROOT%\hooks\cp_hook.cmd <HookName>` 启动，规避 Codex 0.150.1 对带引号 Hook 命令的解析问题。
- `cp_hook.cmd` 优先寻找本机账户 CPython，再回退 PATH 中的 `python.exe` 或 `py.exe -3`；不创建、也无需额外创建 `python3.exe`。
- Hook 使用原始字节读取 stdin，并以 UTF-8 输出；兼容 Windows 中文 Stop payload 截断，仍能恢复生命周期身份字段并返回合法中性 JSON `{}`。
- 观测写入失败保持 fail-open；PreToolUse 模型门禁保持 fail-closed。
- 自动子 Agent 显式模型采用精确 allowlist，仅允许 `gpt-5.6-luna` 与 `gpt-5.6-terra`；`xhigh/max/ultra`、Sol、未知模型和未来 Terra 名称均拒绝自动派发。
- 安装器原子 staging 名称缩短，并在备份、复制、验证、卸载和回滚 I/O 边界统一使用 Windows extended-length path；长账户目录下连续安装、升级备份与恢复不再受 legacy MAX_PATH 限制。
- 卸载 `AGENTS.md` 与 standalone `hooks.json` 时只恢复本包受管区块/精确命令 Hook，保留安装期间新增或修改的外部内容；畸形现有配置失败关闭且不覆盖。
- Windows 安装测试同时隔离 `HOME` 与 `USERPROFILE`，使用 fake `codex.cmd`、超长目录和无需管理员权限的 Junction 测试升级恢复与 Reparse Point 防护。
- 自然语言说明、规则、Reviewer 提示和测试身份统一采用中性表达；CLI 参数、JSON 字段和路径变量等机器契约不变。

## 保持不变

- 10 个工程 Skills、7 个专业 Reviewer、6 个生命周期 Hooks。
- TaskOutcomeEvent V2、SHA-256 事件链、`project_id + repo_fingerprint` 双重项目隔离。
- Luna Low → Luna Medium → Terra Medium → Terra High 自动成本路线，自动上限 Terra High。
- 主 Agent 模型保持外部选择；Reviewer TOML 不写死模型。
- `execution_authorization=NONE`；Proposal 不自动接受、执行或修改 Skill。
- 不自动提交、推送、部署、重启、写生产数据或操作生产环境。
- 安装事务的 dry-run、备份、漂移检测、回滚和未知外部文件保护。

## 兼容性

- 目标宿主：Windows 原生 Codex CLI 0.150.1。
- 支持从 V6.1、V6.0 及 manifest 中列出的旧版本升级。
- V6.1 项目上下文、Event、Snapshot、Assessment、Proposal、Decision 和生命周期记录继续复用，不执行迁移或删除。
- Plugin 成功标准仍为 `codex plugin list --json` 中目标项同时满足 `installed=true`、`enabled=true`、`version=6.2.0`。

## 升级提示

1. 解压 ZIP，不要直接在 ZIP 内运行。
2. 执行 `doctor` 和 Plugin dry-run。
3. dry-run 无阻断后执行账户级 Plugin 安装。
4. 执行 `verify` 和 `codex plugin list --json`。
5. 关闭并重新打开升级前已经存在的 Codex 任务。

完整步骤见 `docs/USER_GUIDE_V6.2.md`。
