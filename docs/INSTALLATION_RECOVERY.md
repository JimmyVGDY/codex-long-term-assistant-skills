# V7.4 安装、验证与事务恢复

## 适用范围

- 目标宿主：Windows 原生 Codex CLI 0.153.2。
- Python：3.11 或更高版本。
- 推荐形态：账户级 Plugin。
- 可升级版本：7.3.0、7.2.0、7.1.0、7.0.0、6.6.1、6.6.0、6.5.0、6.4.0、6.3.0、6.2.0、6.1.0、6.0.0、5.1.0、5.0.0、4.2.0、4.1.0、4.0.0。
- 受管对象：本包 Marketplace payload、manifest 条目、Plugin cache、Reviewer、全局规则和安装状态。

安装器不改写 `config.toml`，不删除未知 Skill、Agent、Hook、MCP、项目上下文、Event、Snapshot、Assessment、Proposal 或历史备份。

## 路径规则

- Skill：`$HOME/.agents/skills`
- Reviewer：`${CODEX_HOME:-$HOME/.codex}/agents`
- 全局规则：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- Marketplace：`$HOME/.agents/plugins/cp-assistant-marketplace`
- state：`${CODEX_HOME:-$HOME/.codex}/cp-assistant-v6-state.json`

Windows 原生进程若继承 `/mnt/c/.../.codex`，必须转换为盘符路径。路径目标及其祖先、受管树后代均不得含符号链接、Junction 或 Reparse Point。

## 标准升级

在解压后的 V7.4.3 语言包根目录依次执行：

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

dry-run 应明确显示：

- 当前升级应读回已安装版本与 `to_version=7.4.3`；V7.4.2 升级路径必须被识别；
- schema 2 保持不变，旧 schema 1 才迁移到 2；
- 新升级备份路径；
- Marketplace payload、manifest 和 Plugin cache 分离目标；
- 未知条目保留；
- 完整回滚动作；
- 无路径越界或链接型路径风险。

Codex 0.153.2 的本地 Marketplace manifest 必须包含顶层 `interface.displayName`。升级器会在备份后移除旧 `owner`、生成受控的 `interface.displayName`，并保留其他未知外部字段；`codex plugin list --json` 恢复正常后才继续激活。

完成条件：Plugin 精确读回 `installed=true`、`enabled=true`、`version=7.4.3`，schema 3 宿主状态为 `HOST_COMPATIBLE`，并且 10 个 Skill、7 个 Reviewer、6 个 Hook、延迟封印 worker、keyring 和 payload digest 全部通过。`java-backend-engineering`、`python-backend-ai-engineering`、`data-middleware-ai-infrastructure` 和此前废弃的 `vue-frontend-engineering` 不得残留；文件复制完成不构成 Plugin 成功状态。

## 事务与能力探测

安装前 `doctor` 检查：

- Codex 版本精确为 0.153.2；
- `plugin list --json` 可执行；
- Marketplace add/remove 与 Plugin add/remove 命令存在；
- state schema 可识别；
- 无活动事务或可恢复残留；
- 载荷 manifest 与当前源树一致。

首次受管写入前建立互斥锁和 journal。journal 记录旧状态、备份、每个目标的 mutation intent、Plugin 注册阶段、cache 候选路径及新旧 digest。成功提交后活动 journal 被清理，归档记录保留。

## 崩溃恢复

先读取状态：

```powershell
python scripts\package_manager.py status --scope user --mode plugin --json
python scripts\package_manager.py doctor
```

存在未提交事务时执行：

```powershell
python scripts\package_manager.py doctor --recover
```

恢复流程按 journal 所有权处理：

1. 恢复 Marketplace payload 与 manifest；
2. 恢复原 Plugin cache 或清理本次候选 cache；
3. 恢复原 Plugin 版本和启用状态；
4. 恢复 state 与合并型全局规则；
5. 再次读取 Plugin list 与 payload digest。

未知内容、归属漂移、损坏 journal、不完整备份或恢复后读回不一致时停止并保留日志。不得直接递归删除整个 `.codex`、`.agents` 或 plugins 目录。

## 手动回滚

优先使用安装器恢复，不直接复制整棵账户目录：

```powershell
python scripts\package_manager.py recover --scope user
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

若正式安装已提交但需回到旧版本，可从保留的升级备份和旧正式包执行明确版本恢复。恢复完成后应确认原版本 installed/enabled、原 cache digest、原 state、主配置哈希和历史项目上下文数量。

## 卸载

```powershell
python scripts\package_manager.py uninstall --scope user --mode plugin --dry-run
python scripts\package_manager.py uninstall --scope user --mode plugin
```

受管资源发生外部修改时默认拒绝覆盖式卸载。`--force` 只在归属和覆盖影响已经明确时使用。普通卸载不删除项目上下文、自观察数据或历史备份。

## 正式制品验证

```powershell
python scripts\validate-package.py
python scripts\build-release.py verify --archive ..\Codex-Skills-V7.4.3-zh-CN.zip --locale zh-CN
python scripts\release-attestation.py verify --attestation ..\release-attestation-v7.4.3.json --artifact ..\Codex-Skills-V7.4.3-zh-CN.zip
```

`validate-package.py` 调用当前 `validate-v73.py`，检查执行前后的 Git index、受管与未跟踪文件内容、删除状态和链接类型；`--output` 只能写到仓库外。其 `routing_host_observation` 固定为 `NOT_EVALUATED`，不能替代真实宿主路由验收。

机器证明应绑定正式 ZIP SHA-256、确定性构建见证、Codex 版本、Plugin list、生命周期报告、已安装 PreToolUse 模型门禁报告、统一验证报告和安装后的 payload digest。任一证据缺失或哈希不一致时，正式发行结论失败关闭。宿主会话 JSONL 只作诊断旁证，不能替代模型门禁报告。

## Windows Hook

六个 Hook 通过 `cp_hook.cmd` 启动，优先使用可用的账户 CPython，再回退 `python.exe` 或 `py.exe -3`。无需额外创建 `python3.exe`。SessionEnd timeout 为 3 秒；Hook 只构造有上限且不含正文的净化事件，并以命令参数无等待派发 detached worker，不扫描或写入事件链，也不做同步管道写入。Worker 在 Hook 预算外完成稳定身份校验、语义去重、持久化、DPAPI 解密、v2 签名入列和封印；未封印的 `seal_required` 链不会被 Evolution 消费。

升级前已打开的任务可能继续使用旧 Plugin 快照；升级后新建任务完成最终发现验证。不自动重启 Codex。
