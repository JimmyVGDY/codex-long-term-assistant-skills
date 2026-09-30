# V7.14.2 发行说明

V7.14.2 将 Codex Desktop 内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.159.0`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归，不构成独立产品支持轨道。

- 冻结 `0.159.0` 至 `0.153.3` 的当前加前十个稳定版窗口，`0.153.2` 退出活动窗口并继续失败关闭。
- 登记官方 npm、`rust-v0.159.0` 标签提交和源码摘要；Hook、schema 与 apply_patch 合同和 `0.158.0` 一致，继续复用 `result-v158`。
- 上游新增 `instant_interrupt`、欢迎页/页眉/提示改版、warnings viewer、计划阶段滚动、Mermaid 扩展与基于 item 的线程分页，并修复 Windows 控制台窗口闪现、复制格式、空白会话、登录、含 `.aws` 的显式文件系统拒绝及 macOS TLS/代理行为；上游同时移除了提示建议和内置 plugin-creator。
- 修复 Windows 并发 worker 创建同一选择锁时可能把根内恢复 guard 误判为未管理路径的竞态，同时保留词法包含与逐祖先 link/reparse 拒绝。
- 保留 V7.14.1 的 0.158.0 兼容边界及 V7.14.0 Desktop V2 权威审查上下文协议。

包验证、账户安装、Desktop 新进程、提交、推送、CI、标签、Draft、公开 Release 和匿名下载分别读回。
