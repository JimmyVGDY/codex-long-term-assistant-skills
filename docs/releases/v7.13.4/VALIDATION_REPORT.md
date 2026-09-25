# V7.13.4 验证记录

- npm `latest` 与 GitHub `rust-v0.157.0` 均确认其为非预发布稳定版。
- 官方制品完整性、SHA-256、标签提交及 Hook/apply_patch 源码摘要已冻结到注册表。
- 窗口精确覆盖 0.157.0 至 0.153.0；0.152.1 失败关闭。
- 包、运行时、隔离 Plugin、合成 Hook、账户、新进程、CI、标签、资产、provenance 与公开下载门禁分别记录。
- 实际 Desktop 安装、verify/doctor、普通沙箱载荷可读且不可写，以及新进程 Plugin 加载通过。
- 原生 V4 reentry denial 通过；正向 spawn 因 Desktop 消息字段是不透明加密传输值而在计费/创建前以 `V4_REQUEST_MESSAGE_MISMATCH` 拒绝。不削弱正文校验、不伪造回执，也不宣称正向准入通过。

读回前不宣称任何远端或公开状态已完成。
