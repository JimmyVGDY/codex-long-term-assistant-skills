# V7.14.6 验证记录

- npm `latest` 与 GitHub `rust-v0.160.1` 均确认 `0.160.1` 为非预发布稳定版。
- 官方注解标签解析到提交 `d27764b82f7118f674371e6d6e76271d9d606edb`；npm integrity 为 `sha512-f1yrJhwgimKQI1kYQlxdPJcFwkNZxZrbz7Hf89EAcnLqkQ7TiESzr2FgSZn13Ga5RuHjlVUfurzwq10wk9zw2g==`，tarball SHA-256 为 `d84454cfa82f61add78b3270073c6e254923e89657c7f0dd1a88cc5659b4e0c0`。
- discovery、schema、apply_patch handler 与 context 源码摘要均与 0.160.0 合同一致；兼容注册表精确包含 `0.160.1` 到 `0.155.1` 的十一项窗口，0.160.1 使用 `result-v158`，0.155.0 退出，0.155.1 与 `result-v155` 保留。
- 0.160.1 隔离 CLI/Plugin/Hook 单元通过；完整验证通过 816 项包测试与 231 项运行时测试，其中包测试 815 项通过、1 项按既有 POSIX 旧解释器条件跳过。严格双语、链接、文档投影与 MkDocs strict 构建均通过；中英文包双次构建由仓库外 witness 确认可复现，标签工作流重新生成并绑定最终资产摘要。
- 首次完整验证正确暴露一处测试夹具仍引用已退出窗口的 0.155.0，并受当前宿主默认 Restricted 策略阻止测试内 PowerShell 脚本。夹具改为保留版本 0.155.1；随后在相同 staged 基线下仅对验证进程使用 Process-scope Bypass 重跑并通过，未修改账户执行策略。
- 当前账户管理 CLI 读回 `0.160.1`；Plugin install/verify/strict doctor 读回 `7.14.6`、`installed=true`、`enabled=true`、三方 payload digest 一致且 `HOST_COMPATIBLE`。新建的实际 Codex Desktop 只读任务 `01a10e66-333d-78e3-bc88-9b5d9c66b749` 直接确认宿主已注入 V7.14.6 的十个 Skill，捆绑管理组件为 `0.160.0`，并结合账户层独立读回返回 `DESKTOP_ACCEPTANCE_PASS`；管理 CLI 与 Desktop 运行组件版本不互相替代。
- 提交、origin/master、CI、注解标签、唯一 Draft、六个资产、SHA256SUMS、双 witness、provenance、公开 latest 与匿名下载继续作为独立后续门禁。
