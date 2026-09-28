# V7.14.1 验证记录

- npm `latest` 与 GitHub `rust-v0.158.0` 均确认 `0.158.0` 为非预发布稳定版。
- npm integrity、tarball SHA-256、标签提交 `064c6b8c737f5b41d171fdda80bd9ef10ad06eb3`、Windows 二进制和 CLI 输出摘要已独立读取。
- Hook discovery/schema 与 context 摘要保持不变；apply_patch handler 摘要变化已冻结为 `result-v158`。
- 完整验证通过：815 项包测试与 231 项运行时测试完成；0.158.0 隔离 Plugin、CLI 合同和合成 Hook 矩阵通过。
- 当前账户管理 CLI 读回 `0.158.0`；Plugin 安装、verify、doctor 读回 `7.14.1` 与 `HOST_COMPATIBLE`。新启动的 Desktop 捆绑组件 `0.158.0-alpha.2.1` 在只读 ephemeral 进程中返回 `DESKTOP_ACCEPTANCE_PASS`。
- CI、标签、Draft、六资产、SHA256SUMS、witness、provenance、公开 Release 与匿名下载仍是独立门禁。
