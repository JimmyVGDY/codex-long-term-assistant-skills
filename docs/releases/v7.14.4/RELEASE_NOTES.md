# V7.14.4 发行说明

V7.14.4 将 Codex Desktop 内部冻结组件兼容窗口推进到 OpenAI 官方稳定版 `0.159.2`。产品仍仅支持 Codex Desktop；独立 CLI 只用于管理、构建和内部兼容回归，不构成独立产品支持轨道。

- 冻结 `0.159.2` 至 `0.154.0` 的当前加前十个稳定版窗口；`0.159.1` 与 `0.159.2` 同时进入活动窗口，`0.153.4` 与 `0.153.3` 退出并继续失败关闭。
- 分别登记两个补丁版的官方 npm、注解标签提交和源码摘要；Hook discovery/schema 与 apply_patch handler/context 合同和 `0.159.0` 一致，三个 `0.159.x` 版本继续复用 `result-v158`。
- 上游 0.159.1 将 GPT-6.1 Sol 加入捆绑与 Amazon Bedrock 目录，但不改变本包冻结的 Reviewer 资格或生产默认；0.159.2 回移 Windows 后台进程与沙箱命令的控制台窗口抑制修复。
- GitHub Actions 运行 `36846683350` 的 attempts 1-3 在 Windows Python 3.11 上连续达到 1800 秒上限且无断言失败；因此将有界包验证子进程时限从 1800 秒提升到 3600 秒，超时仍生成失败关闭证据。
- 保留 V7.14.3 Desktop-only 兼容边界、master/tag 祖先门禁、Windows 恢复根竞态修复及 V7.14.0 Desktop V2 权威审查上下文协议。

包验证、账户安装、Desktop 新进程、提交、推送、CI、标签、Draft、公开 Release 和匿名下载分别读回。
