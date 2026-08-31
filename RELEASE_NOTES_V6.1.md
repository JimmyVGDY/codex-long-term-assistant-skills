# V6.1 官方插件安装兼容修复版

V6.1 基于 V6.0，针对 Codex CLI 0.150.1 的 Plugin/Marketplace/Hooks 实际加载机制进行兼容修复。

## 修复

- Marketplace manifest 使用 Codex 0.150.1 支持的 `.agents/plugins/marketplace.json` 布局。
- Plugin 模式安装器会实际执行 `codex plugin marketplace add <root>` 与 `codex plugin add <plugin>@<marketplace>`。
- `verify --mode plugin` 不再只检查文件落盘，而是读取 `codex plugin list --json`，要求插件 `installed=true` 且 `enabled=true`。
- Plugin Hooks 同时提供 Unix `command` 与 Windows `commandWindows`，避免 `$PLUGIN_ROOT` 在 `cmd.exe` 下无法展开。
- `SessionEnd` 超时设为 3 秒，与当前 Codex 宿主限制一致。
- 保留 V6 的 10 Skills、7 Reviewer、TaskOutcomeEvent V2、Terra High 自动子代理上限、受控演进权限边界。

- Windows 原生 Python 若继承 `/mnt/c/...` 形式的 `CODEX_HOME`，安装器会转换为原生盘符路径再执行安全检查。
- Plugin 安装失败会撤销可能的部分 Plugin 注册并清理状态文件；Plugin 卸载会先调用 `codex plugin remove` 再恢复受管文件。
