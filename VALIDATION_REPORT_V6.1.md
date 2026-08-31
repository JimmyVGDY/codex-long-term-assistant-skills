# V6.1 最终验证报告

- 目标版本：6.1.0
- Codex 兼容目标：0.150.1
- Python 语法编译：PASS
- 单元/回归测试：20/20 PASS
- `scripts/validate-package.py`：PASS
- Skills：10
- Reviewers：7
- Hooks：6（UserPromptSubmit / PreToolUse / SubagentStart / SubagentStop / Stop / SessionEnd）
- TaskOutcomeEvent：2.0
- execution_authorization：NONE
- 自动自修改：禁用
- 路由用例 Schema：35 cases PASS
- Plugin 安装事务：PASS（模拟 Codex 0.150.1 CLI）
- Plugin verify：PASS（要求 installed + enabled）
- Plugin uninstall/Marketplace cleanup：PASS
- Standalone install/verify/uninstall：PASS
- Windows WSL-style CODEX_HOME 原生路径转换：已实现
- 真实 Codex 0.150.1 Windows 端到端：需用户实机安装后验收

## V6.1 关键修复

1. Marketplace manifest 使用 Codex 0.150.1 支持的 `.agents/plugins/marketplace.json` 布局。
2. Plugin 模式安装器实际调用 `codex plugin marketplace add <root>` 和 `codex plugin add <plugin>@<marketplace>`。
3. Plugin verify 通过 `codex plugin list --json` 检查 installed + enabled，而非仅检查文件落盘。
4. Hooks 同时配置 `command` 和 `commandWindows`；Windows 不再依赖额外创建 `python3.exe`。
5. SessionEnd timeout 固定为 3 秒，与 Codex 0.150.1 宿主限制一致。
6. Windows 原生 Python 若继承 `/mnt/c/...` 形式的 CODEX_HOME，会转换为原生盘符路径后再执行安全检查。
7. Plugin 安装失败会撤销部分注册并恢复旧状态；卸载会清理 Plugin/Marketplace 注册，并在升级回滚场景恢复旧版状态。
