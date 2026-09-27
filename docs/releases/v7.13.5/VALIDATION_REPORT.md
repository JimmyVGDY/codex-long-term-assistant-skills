# V7.13.5 验证记录

- npm `latest` 与 GitHub `rust-v0.157.1` 均确认 `0.157.1` 是非预发布稳定版；官方 Release 未提供可核验的功能亮点。
- npm integrity、tarball SHA-256、官方标签提交 `36650394c5b38c2990ccf2a3457165ca3e9d9726`、Windows 二进制摘要与精确 CLI 输出摘要已独立读取。
- Hook discovery、Hook schema、apply_patch handler/context 的官方源码摘要与 `0.157.0` 一致；十一版本标签与源码证据已按注册表复核。
- 完整包验证通过：780 项包测试与 231 项运行时测试完成；0.157.1 隔离 Plugin、CLI 合同和合成 Hook 矩阵通过。
- 当前账户全局 Codex 读回 `0.157.1`；重装后 doctor 为 `PASS`，Plugin 读回 `7.13.5`、`installed=true`、`enabled=true`。新启动的 Desktop 捆绑组件 `0.158.0-alpha.2.1` 在只读 ephemeral 进程中返回 `DESKTOP_ACCEPTANCE_PASS`。
- CI、标签、Draft、六个资产、SHA256SUMS、witness、provenance、公开 Release 与匿名下载继续作为独立门禁。
