# V7.11.2 验证报告

## 已验证

- OpenAI 官方 changelog 与 npm `latest` 均指向 Codex CLI 0.155.1；GitHub `rust-v0.155.1` 为非预发布稳定发行。
- npm integrity 与 tarball SHA-256 已冻结；官方标签 commit 为 `be2951ea34f0d295ed0becf97079f92fa5f6950e`。
- Hook discovery、Hook schema 与 apply_patch result 源码合同摘要与 0.155.0 保持一致。
- Windows 0.155.1 版本输出、Plugin/Marketplace 命令帮助、空 Plugin 列表、隔离 Plugin 预检与合成 Hook 合同通过。
- 当前加前十个稳定发行版的闭合窗口已写入注册表，0.150.1 已移出。

## 独立门禁

完整包测试、运行时测试、双语构建、可重复构建、独立复审、账户安装、新进程验收、主分支 CI、稳定版兼容矩阵和标签发布工作流在交付阶段分别执行并读回。本文不以本地验证替代远端发布状态。

当前候选记录 `RELEASE_COMPLETE=false` 与 `INCIDENT_EFFECTIVE=UNVERIFIED`；二者必须独立更新，不能用发布完成推断已打开会话或其他事件状态已生效。
