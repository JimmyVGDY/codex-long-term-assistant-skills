# V7.9.0 发行说明

English: [Release notes](RELEASE_NOTES.en.md)

V7.9.0 将 Plugin 拆分为可直接安装的基础能力和按需接入的增强运行时。

- 新增无需本包 Python 或 API Key 的基础原生安装入口；基础路径仅加载十个 Skill。
- Hook、长期状态、预算、受控写入、账户工具、全局规则和 Reviewer 转为增强安装事务管理；基础路径不启动这些组件。
- 增强安装复用现有备份、journal、verify、recover 与漂移保护；基础升级到增强和增强卸载恢复基础均有隔离回归。
- `doctor` 与 `status` 默认输出可用能力、受影响项、原因和下一步；`--json` 保留详细机器格式。
- 简单局部任务默认由主 Agent 串行完成，不主动派发子 Agent、全仓扫描或长期检查点；严格预算只在真实宿主绑定可核验时强制执行。

已公开发布：提交 `bd73b30`、标签 `v7.9.0`、双语 ZIP 与可重复构建见证均已读回。当前账户增强安装、`verify` 和项目外新 CLI 任务亦已通过。Desktop 重启加载、Ubuntu 和 macOS 实机路径仍为 `UNVERIFIED`，不据此宣称支持。
