# V6.6 Release Notes

版本：6.6.0  
目标宿主：Windows 原生 Codex CLI 0.150.1

## 新增

1. 增加可信宿主实际模型证明契约。证明必须绑定 issuer、attestation id、有效期、Hook、session、turn、agent、模型和推理强度，并通过外部信任锚校验。
2. 增加 Windows spawn 真多进程、强制终止、PID 复用、keyring 与 seal 原子替换断点测试。
3. 增加 SessionEnd 签名队列与 detached worker。SessionEnd 不执行全链扫描或封印；入列或启动失败输出不含正文的明确诊断。
4. Reviewer 校准增加任务难度分布、根因簇重复、采纳原因和带回归证据的预防收益。
5. 增加非破坏事件归档、容量预算和隐私受限的跨项目健康概览；reparse 越界失败关闭，单项目损坏隔离。
6. 固定区分三个模型字段：

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

## 兼容

- TaskOutcomeEvent 保持 2.0；V6.0–V6.5 历史记录不改写。
- V6.5 keyring 原位兼容，RETIRED key 保留并继续验证历史 seal 与 attestation。
- 10 个 Skill、7 个 Reviewer、6 个 Hook 和 Terra High 自动上限保持不变。
- 主 Agent 模型配置不改写，Reviewer TOML 不固定模型。
- `execution_authorization=NONE`、人工 Proposal 决策和无自动提交/推送/部署边界保持不变。

## 当前宿主限制

Codex 0.150.1 未向 Hook 提供可由外部信任锚验证的实际模型证明。因此模型请求策略和生命周期可通过，但实际运行模型必须保持 `UNAVAILABLE`；rollout 中的模型与强度只作为 `DIAGNOSTIC`。
