# V7.4.0 验证报告

状态：本地包验证、真实账户级安装和实施后复审通过。

- Python 3.13.15 完整包验证：198 项包测试、6 项运行时测试全部通过。
- 语义校验、45 个路由场景、模型上限、payload 完整性和工作区无副作用门禁均为 PASS。
- 中英文 ZIP 均完成两次独立构建并取得相同摘要，归档结构与规范化时间戳验证通过。
- Codex CLI 0.153.0 账户级 Plugin 从 V7.3.0 强制升级到 V7.4.0；安装器 verify/status/doctor 通过。
- `codex plugin list --json` 独立读回 `installed=true`、`enabled=true`、`version=7.4.0`。
- 源目录、Marketplace 与 Plugin cache 均为 182 个受管文件，payload digest 一致。
- V7.2.0 与 V7.3.0 缺失 `interface.displayName` 的 Marketplace 快照均有独立升级回归测试。

本机未安装 Python 3.11；Python 3.11 与跨平台矩阵由标签后的 GitHub Actions 验证，结果属于包外发布证据。公开 Release、远端标签与 CI 状态也必须在发布后单独读回，不能由本报告预先宣称。

V7.4.0 只验证 Codex CLI 0.153.0。当前版本加前十个稳定版的兼容窗口明确延后到 V7.4.1。
