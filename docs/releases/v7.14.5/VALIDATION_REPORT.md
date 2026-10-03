# V7.14.5 验证记录

- npm `latest` 与 GitHub `rust-v0.160.0` 均确认 `0.160.0` 为非预发布稳定版。
- npm integrity `sha512-kEtV...lpjg==`、tarball SHA-256 `373517768e912eeb5054024ae9215e2c90a1420957b66fe134ef745a00948d4a` 与官方注解标签提交 `a956835d020762cb2b570053af06f643a11c0ecc` 已独立读取。
- Hook discovery/schema、apply_patch handler 与 context 摘要分别为 `fd05ee...72b04`、`162735...3e14`、`75cc61...0cad` 与 `9a9acc...e00cc`，和当前 `result-v158` 合同一致。
- 兼容注册表精确包含 `0.160.0` 至 `0.155.0` 的十一项窗口；0.160.0 使用 `result-v158`，0.154.0 与已无使用方的 `result-v154` 均退出。
- 0.160.0 隔离 CLI/Plugin/Hook 单元通过；完整验证通过 816 项包测试与 231 项运行时测试。严格双语、链接、文档投影与 MkDocs 构建均通过；中英文包双次构建均由仓库外 witness 确认可复现，最终资产摘要由标签工作流重新生成并绑定。
- 当前账户管理 CLI 读回 `0.160.0`；Plugin install/verify/strict doctor 读回 `7.14.5`、`installed=true`、`enabled=true`、三个 payload digest 一致且 `HOST_COMPATIBLE`。实际 Codex Desktop 捆绑组件的新 ephemeral 只读进程 `0.160.0` 返回 `DESKTOP_ACCEPTANCE_PASS`。
- 实施前逻辑只读复审采纳 `result-v154` 原子删除回归，并驳回会混淆稳定窗口与实际 Desktop host contract 的绑定建议；实施后复审单独记录。
- CI、注解标签、Draft、六个资产、SHA256SUMS、witness、provenance、公开 Release 与匿名下载继续作为独立门禁并在源快照之外读回。
