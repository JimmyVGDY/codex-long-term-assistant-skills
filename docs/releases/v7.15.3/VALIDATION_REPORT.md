# V7.15.3 验证记录

- npm `latest` 与 GitHub `rust-v0.162.1` 均确认 `0.162.1` 为非预发布稳定版；`0.162.0` 同样由正式注解标签与 npm 包冻结。
- `0.162.1` 注解标签解析到提交 `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`；npm integrity 为 `sha512-NWZdi/kxyjv/8EUGFupziGU38YyleugZRM4JXgY5XFH7FUmaFA33NZS2Bmq0HPazf7S3jJQQWsZ/jAK9jsrV3Q==`，tarball SHA-256 为 `0b4b2e33a65883e4f69c903484d8dd7770b3cb8b324f520068b6fd85d42b65ea`。
- `0.162.0` 注解标签解析到提交 `c1382380de69521303b416720a52f42d51af6248`；npm integrity 为 `sha512-qWWckMfknyVym1lD5y2rTwPJA2sgHkzePF2l/Uevss4hVpqbt23rMIHKNTrqECdnv82denylHWEzrAmDnCYNIw==`，tarball SHA-256 为 `6cb67d6e7631af84f27580d8fe228ac437c34181d370dc5c5a5819e014c8c860`。
- 0.162.x discovery 摘要为 `763704f5ae5f227d186dae8f5339edd6fde4f4a54c88c8ffb5ef9ad1b5a368eb`，schema 为 `162735b4d0c021c911cb3939b6130d2aad90cf5f865069a17b97c0cf02c53e14`，apply_patch handler 为 `1256b2219f6acb9c49ae472860ee69d73c75bb427dcca4dae2a30018d30216c0`，context 为 `9a9acc6daab2112bd9ca1a07a1e1f2105b20a7f565878157c726ee0d7a3e00cc`。
- 兼容注册表精确覆盖 `0.162.1` 到 `0.157.0` 的十一项窗口；0.162.1 与 0.162.0 的 Windows CLI/Plugin/Hook 隔离单元已通过。完整验证通过 1148 项包测试与 231 项运行时测试，其中包测试 1147 项通过、1 项按既有 POSIX 旧解释器条件跳过；包与运行时报告摘要分别为 `6abe62ecc077bdfae01ece2ce8ca11c934f6868fb93df6d993f1aa74427ecb1d` 和 `4c624838fde57a78cc1437b456bfc723346f6de8481fe212c93fe0e063fe8345`。
- 账户管理 CLI 已独立更新并读回 `codex-cli 0.162.1`；V7.15.3 Plugin 的 install、verify、strict doctor 与 `codex plugin list --json` 均通过，322 个 payload 文件摘要一致。fresh Codex Desktop task 读回 `loaded_plugin=7.15.3`、`skills=10` 与实际捆绑组件 `codex-cli 0.162.0-alpha.2`；管理 CLI、账户 Plugin 和 Desktop 捆绑组件仍按分层证据记录，不互相冒充。
- 提交、origin/master、CI、注解标签、唯一 Draft、六项资产、SHA256SUMS、双 witness、provenance、公开 latest 与匿名下载均保持后续门禁。
