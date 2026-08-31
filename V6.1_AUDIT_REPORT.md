# V6.1 审查与修复报告

## 基线

基于 V6.0 安装包与实际 Windows 安装报告复核。安装报告显示 V6.0 最终能通过人工兼容处理实现 Plugin、6 Hooks、10 Skills、7 Reviewers 的真实加载；同时暴露了 `python3.exe`、Marketplace manifest 布局和安装器仅提示后续注册的问题。

## V6.1 修复

1. Marketplace 布局改为 `.agents/plugins/marketplace.json`。
2. Plugin 安装器直接调用 Codex CLI 完成 Marketplace 注册和 `plugin add`。
3. Verify 读取 `codex plugin list --json`，必须 installed+enabled。
4. Hooks 使用 `commandWindows`/`command` 双通道，Windows 不再依赖人为创建 `python3.exe`。
5. SessionEnd timeout=3s。
6. 保留受控演进与 Terra High 上限。

## 仍需实机验收

- Codex 0.150.1 首次 Hook trust UI。
- Windows 原生 CLI 下 6 Hook 生命周期。
- 实际子 Agent PreToolUse 阻断。

- Windows 原生 Python 若继承 `/mnt/c/...` 形式的 `CODEX_HOME`，安装器会转换为原生盘符路径再执行安全检查。
- Plugin 安装失败会撤销可能的部分 Plugin 注册并清理状态文件；Plugin 卸载会先调用 `codex plugin remove` 再恢复受管文件。
