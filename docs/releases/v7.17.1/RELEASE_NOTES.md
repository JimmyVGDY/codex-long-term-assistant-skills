# V7.17.1 发行说明

V7.17.1 是基于已公开 V7.17.0 的 Codex Desktop 内部组件兼容补丁。它把冻结兼容窗口推进到 OpenAI 官方稳定版 0.163.0 与此前十个稳定发行版，移除窗口末端的 0.157.0；产品范围仍仅限 Codex Desktop，不建立独立 CLI 支持轨道。

- 官方 `rust-v0.163.0` 标签解析到提交 `83086188ae0614bd882818ff1aa23f3194962012`。
- npm integrity 为 `sha512-HNd7vR9oTK6M2ikxFnvNDCdYUgAsyo9VVnd5KnEd2ON0GYI++7MiX9XNPUkhtdgGKFPsWS+CEppQ1UU63uVhUw==`，tarball SHA-256 为 `1a71db36560bb446d2c2e63ae675c4a3018c38ace38ca533f8d1b25d3e6555b4`。
- 0.163.0 的 Hook discovery、Hook schema、apply_patch handler 与 context 摘要均与 0.162.x 一致，因此继续使用已冻结的 `result-v162`，不新增未经证实的协议分支。
- Windows 隔离版本、Plugin JSON、Marketplace/Plugin 帮助命令、Plugin 预检和合成 Hook 合同已按 0.163.0 重放。
- 0.163.0 的 `/config`、即时跟随和中断、leader key、后台服务重启、只读工具并行、权限恢复和网络代理修复不自动改变本包的 Reviewer、预算、TaskScope 或 Operation v2 合同。

V7.17.0 的六项 Skill 质量流程、任务额度和门禁恢复实现保持不变。正式发布前仍需在当前提交上完成完整包、运行库、文档、可复现构建、独立复审、账户 Plugin 与实际 Desktop 进程验收；未完成的步骤不得由本说明冒充为 PASS。
