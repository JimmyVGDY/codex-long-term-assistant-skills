# V6.5 Release Notes

版本：6.5.0  
目标宿主：Windows 原生 Codex CLI 0.150.1

## 主要变化

1. 新增 `host_facts` 适配器。宿主会话 JSONL 采用稳定读取、大小限制、Reparse 拒绝、父会话与子任务关联及冲突检测；输出只保留摘要。该来源固定为 `DIAGNOSTIC`，不能单独证明模型门禁或发行状态。
2. 新增 Integrity Keyring V1。Windows 使用当前账户 DPAPI，POSIX 使用 0600 文件；`event-hmac` 与 `release-attestation` 两种用途独立，支持保留历史密钥的轮换。
3. 新增 detached event seal。封印独立于 TaskOutcomeEvent 2.0 原始记录，绑定链头、记录数、前一封印、issuer 和 key id。V6.4 进程继续写入时形成合法未封印尾部，不破坏历史封印。
4. 新增 Reviewer Calibration V1。按稳定 `result_id` 去重并检测冲突，输出独立任务数、归因覆盖、Wilson 95% 区间、成本/收益与校准状态。
5. 发行 attestation 支持 keyring HMAC 轮换，并拒绝 host-only 模型证明、未封印的当前事件链头和 keyring/legacy 模式降级。真实生命周期与已安装 PreToolUse 模型门禁分开验收，避免把 Codex 0.150.1 的诊断会话记录冒充可信 Hook 模型事实。

## 保持不变

- 10 个 Skill、7 个 Reviewer、6 个 Hook；
- TaskOutcomeEvent schema 2.0；
- Plugin ID 与 Marketplace ID；
- 自动子 Agent 路线与 Terra High 上限；
- Reviewer TOML 不固定模型，主 Agent 模型不覆盖；
- `execution_authorization=NONE`；
- 不自动修改能力、不自动接受 Proposal、不自动提交、推送、部署、重启或操作生产环境；
- V6.4 项目上下文、事件、Snapshot、Proposal 与升级备份保留。

## 升级

V6.4.0 可直接通过 Plugin 模式升级。安装器仍以 `doctor -> dry-run -> install -> verify -> codex plugin list --json` 为正式路径。
