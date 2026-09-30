# V7.14.2 验证记录

- npm `latest` 与 GitHub `rust-v0.159.0` 均确认 `0.159.0` 为非预发布稳定版。
- npm integrity、tarball SHA-256、精确 CLI 输出摘要与官方标签提交 `687a119f0fcaace47e1f1abcc77cec6c813fd6da` 已独立读取。
- Hook discovery/schema、apply_patch handler 与 context 摘要和 `0.158.0` 一致；两个版本共同使用冻结的 `result-v158` profile。
- 完整包验证通过 815 项包测试与 231 项运行时测试；0.159.0 固定制品、CLI 合同、隔离 Plugin 与合成 Hook 矩阵通过。
- 首轮完整验证出现一个无关的运行时计时失败；该用例隔离复查三次通过，但后续完整轮次在另一个包测试中重现 Windows 根选择竞态。修复在保留词法包含与逐祖先 link/reparse 拒绝的同时消除了竞态；并发用例重复 200 次及最终完整 815+231 轮次通过。
- 当前账户管理 CLI 读回 `0.159.0`；Plugin 安装、verify、doctor 读回 `7.14.2` 与 `HOST_COMPATIBLE`。新启动的只读 ephemeral Desktop 捆绑组件进程 `0.158.0-alpha.2.1` 返回 `DESKTOP_ACCEPTANCE_PASS`。
- CI、注解标签、Draft、六个资产、SHA256SUMS、witness、provenance、公开 Release 与匿名下载继续作为独立门禁。
