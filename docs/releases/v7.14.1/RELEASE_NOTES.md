# V7.14.1 发行说明

V7.14.1 将 Codex Desktop 内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.158.0`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归，不构成独立产品支持轨道。

- 冻结 `0.158.0` 至 `0.153.2` 的当前加前十个稳定版窗口，`0.153.1` 退出活动窗口并继续失败关闭。
- 登记官方 npm、`rust-v0.158.0` 标签提交和源码摘要；Hook discovery/schema 与 context 合同不变，apply_patch handler 变化由仅供 `0.158.0` 使用的 `result-v158` 描述。
- 上游新增 TUI 复制/粘贴、MCP OAuth client secret、exec-server bearer token、透明背景图像和终端输入审批，并修复 Windows/Linux/macOS 沙箱、审批重试、Mermaid 与命令完成事件；本包只记录与 Desktop 管理及运行边界相关的可核验证据。
- 保留 V7.14.0 Desktop V2 权威审查上下文协议、版本化预算和交付凭证。

包验证、账户安装、Desktop 新进程、提交、推送、CI、标签、Draft、公开 Release 和匿名下载分别读回。
