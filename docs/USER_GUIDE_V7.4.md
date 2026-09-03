# Codex 跨项目长期技术助手 V7.4 使用说明

## 1. 本版重点

V7.4.1 保留 Reviewer、Explorer、Worker 的同一个根任务加权预算。Task Envelope 声明预算档位，`delegation-budget.py` 维护仓库外追加式账本，PreToolUse Hook 在派发前原子预占，Reviewer 控制器只维护复审轮次与 Finding，不再重复计费。

模型权重固定为：`luna-low=1`、`luna-medium=2`、`terra-medium=4`、`terra-high=8`。初始预算为：

| 档位 | 单位 | 派发 | 并行 | 深度 | Terra High |
|---|---:|---:|---:|---:|---:|
| LIGHT | 4 | 2 | 1 | 1 | 0 |
| STANDARD | 16 | 6 | 3 | 2 | 1 |
| STRICT | 32 | 10 | 3 | 2 | 1 |

## 2. 使用顺序

1. 在仓库外初始化 Task Envelope，并选择 `LIGHT`、`STANDARD` 或 `STRICT`。
2. 在仓库外初始化 DelegationBudget V1 账本。
3. 每次派发前先记录 `INLINE` 或 `DELEGATE` 决策。DELEGATE 必须使用受控原因码，并以不含任务正文的唯一 dispatch key 作为 permit。
4. 在 Codex 宿主启动环境中设置 `CP_DELEGATION_BUDGET_PATH` 指向账本，并同时设置 `CP_DELEGATION_BUDGET_REQUIRED=1`。PreToolUse 只有在稳定宿主派发 ID、角色、模型档位与 permit 全部匹配时才允许并原子预占；Required 模式缺少账本路径时会失败关闭。
5. 宿主能够传播 `reservation_id` 时，由 SubagentStart/Stop 自动对账；Codex 0.153.0 未传播时保持 `RESERVED`，不得靠时间顺序猜测。
6. 只有宿主明确证明 Agent 未启动时才能释放预占。Agent 一旦启动，完成、失败或取消都不退款。

示例：

```powershell
python scripts\delegation-budget.py init --ledger C:\safe-state\budget.jsonl --budget-id BUDGET-1 --task-id TASK-1 --project-id PROJECT-1 --repo-fingerprint sha256:<64-hex> --budget-class STANDARD --default-model-profile luna-medium
python scripts\delegation-budget.py decide --ledger C:\safe-state\budget.jsonl --dispatch-key review-data-1 --decision DELEGATE --role reviewer --requested-profile luna-medium --reason-code INDEPENDENT_EVIDENCE_GAIN
```

V7.4.1 不会自动为每个根任务创建账本。统一预算采用任务级显式激活；未设置上述两个环境变量时，Hook 仍执行自动模型上限，但不得把该任务记录为“统一预算门禁已通过”。

## 3. 路由原因

允许：`INDEPENDENT_EVIDENCE_GAIN`、`SEMANTIC_COMPLEXITY`、`EVIDENCE_CONFLICT`、`SECURITY_OR_CONCURRENCY_RISK`、`LOWER_TIER_INCONCLUSIVE`、`MISSING_EVIDENCE`、`INLINE_SUFFICIENT`。

- `MISSING_EVIDENCE` 不能用于模型升级。
- `LOWER_TIER_INCONCLUSIVE` 必须引用上一档结果，并且只允许逐级升级。
- Terra High 只允许高风险安全/并发直达，或有上一档结果的逐级升级。
- 未知角色、非法模型组合、非法原因码或损坏账本失败关闭。

## 4. 实际模型与校准

未显式指定模型时按 Task Envelope 默认档位计费，依据写为 `policy-default`，不能写成实际模型已验证。普通 Hook payload 也不是可信实际模型证明。只有与 reservation 关联的宿主签名证明同时给出 model 和 reasoning effort 时，才允许实际档位补扣。

Reviewer、Explorer、Worker 使用不同收益指标。子 Agent 自报只能形成 pending 样本；主协调 Agent 带 SHA-256 Evidence 引用最终化后，样本才可进入离线回放。缺可信实际档位或相邻档位样本不足时，结果必须为“不调整”。Proposal 永久保持 `execution_authorization=NONE`。

## 5. Codex 0.153.0 边界

V7.4.1 的 Plugin 窗口是 Codex CLI 0.153.0 与此前十个稳定发行版，精确列表由 `config/codex-compatibility-v1.json` 冻结。本地 Marketplace manifest 必须包含 `interface.displayName`；未来版、预发布版和其他窗口外版本不会自动接纳。

安装完成必须读回 `installed=true`、`enabled=true`、`version=7.4.1`，且 schema 3 宿主快照为 `HOST_COMPATIBLE`。磁盘已有文件不等于 Plugin 已注册或已启用。
