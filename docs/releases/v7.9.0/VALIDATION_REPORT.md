# V7.9.0 验收记录

English: [Validation record](VALIDATION_REPORT.en.md)

## 已验证发布证据

- Windows 隔离 Codex Home 已完成基础安装、基础升级增强、增强 verify、增强卸载和基础恢复；基础安装不写增强 runtime 或 Hook。
- 完整包验证通过：433 个包级测试、205 个运行时测试；发行、隐私、调度和 payload 门禁均为 `PASS`。
- 独立复审发现的基础 state 迁移、失败恢复、Hook 漂移验证和链接祖先防护问题已集中修复并定向复核通过。
- 已推送提交 `bd73b30` 和标签 `v7.9.0`，公开 Release 含中英文 ZIP 与各自可重复构建见证。
- 当前账户已安装并验证 `installed=true`、`enabled=true`、`version=7.9.0`、`HOST_COMPATIBLE`；项目外新 CLI 任务直接完成基础能力响应，未创建 Profile、未扫描目录、未调用工具。
- 当前账户的状态摘要能区分基础 Plugin 宿主漂移和增强缺失；磁盘 state 不能替代实际宿主加载。

## 仍未验证的组合

- Ubuntu、macOS 实机安装路径与 Desktop 重启后的新会话加载。
- 远端 GitHub Actions 的本次执行状态应以 Actions 页面为准；本记录不以本地测试替代远端 CI。
- 任何缺少真实环境的组合保持 `UNVERIFIED`，不得推断为支持。

## 状态分离

- 发布已经读回提交、推送、标签、公开资产、隔离安装与账户安装。Desktop 未重启，因此未报告 Desktop 加载完成。
