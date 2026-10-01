# V7.14.3 验证记录

- npm `latest` 与 GitHub `rust-v0.159.2` 均确认 `0.159.2` 为非预发布稳定版。
- npm integrity、tarball SHA-256、精确 CLI 输出摘要与官方标签提交 `8e68a98ef03cdde76d2e6800791ebdf1b3b95b24`（0.159.1）和 `ff6aec96948b70d94983af2641a6b67c94faeff5`（0.159.2）已独立读取。
- Hook discovery/schema、apply_patch handler 与 context 摘要和 `0.159.0` 一致；三个 `0.159.x` 版本共同使用冻结的 `result-v158` profile。
- 0.159.1 与 0.159.2 的 Windows 隔离 CLI/Plugin/Hook 单元均通过；完整包验证通过 815 项包测试与 231 项运行时测试。
- 当前账户管理 CLI 读回 `0.159.2`；Plugin 安装、verify、doctor 读回 `7.14.3` 与 `HOST_COMPATIBLE`。新启动的只读 ephemeral Desktop 捆绑组件进程 `0.158.0-alpha.2.1` 返回 `DESKTOP_ACCEPTANCE_PASS`。
- CI、注解标签、Draft、六个资产、SHA256SUMS、witness、provenance、公开 Release 与匿名下载继续作为独立门禁。
