# V6.5 包内验证报告

版本：6.5.0  
范围：源码树与自动化验证；不替代真实 Codex Plugin 读回、生命周期和发行 attestation。

## 已验证能力

- Python/JSON/TOML 语法与结构；
- 10 个 Skill、7 个 Reviewer、6 个 Hook；
- Windows Hook 跨平台启动与 SessionEnd 3 秒超时；
- Plugin payload digest、ZIP 路径安全与确定性构建；
- 安装事务、dry-run、恢复和未知文件保护；
- TaskOutcomeEvent 2.0、segment、半记录恢复与哈希链；
- 宿主事实诊断信任边界；
- DPAPI/POSIX keyring、轮换、binding 失败关闭；
- V6.4 混合写入、未封印尾部与跨 key 封印；
- Reviewer 结果重放、冲突、样本充分性与校准状态；
- Terra High 自动上限与 Sol/xhigh 拒绝；
- 真实生命周期与已安装 PreToolUse 模型门禁证据分离，DIAGNOSTIC 宿主模型记录不作为发行通过条件；
- `execution_authorization=NONE` 和 Proposal 人工决策边界。

最终测试数量、正式 ZIP 哈希、真实安装路径和 Plugin 状态在包外升级报告中记录。
