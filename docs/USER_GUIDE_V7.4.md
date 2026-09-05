# Codex 跨项目长期技术助手 V7.4 使用说明

## 1. 本版重点

V7.4.6 保留 Reviewer、Explorer、Worker 的同一个根任务加权预算，并把模型身份隐私边界收紧到派发之前。Task Envelope 声明预算档位，`delegation-budget.py` 维护仓库外追加式 Budget V2 账本，PreToolUse Hook 在派发前按批准档位原子预占，Reviewer 控制器只维护复审轮次与 Finding，不再重复计费，也不接收宿主运行时模型身份。

模型权重固定为：`luna-low=1`、`luna-medium=2`、`terra-medium=4`、`terra-high=8`。初始预算为：

| 档位 | 单位 | 派发 | 并行 | 深度 | Terra High |
|---|---:|---:|---:|---:|---:|
| LIGHT | 4 | 2 | 1 | 1 | 0 |
| STANDARD | 16 | 6 | 3 | 2 | 1 |
| STRICT | 32 | 10 | 3 | 2 | 1 |

## 2. 使用顺序

1. 在仓库外初始化 Task Envelope，并选择 `LIGHT`、`STANDARD` 或 `STRICT`。
2. 在仓库外初始化 DelegationBudget V2 账本。
3. 每次派发前先记录 `INLINE` 或 `DELEGATE` 决策。DELEGATE 必须使用受控原因码，并以不含任务正文的唯一 dispatch key 作为 permit；精确模型请求只允许在宿主适配器校验期间短暂存在。
4. 在 Codex 宿主启动环境中设置 `CP_DELEGATION_BUDGET_PATH` 指向账本，并同时设置 `CP_DELEGATION_BUDGET_REQUIRED=1`。PreToolUse 只有在稳定宿主派发 ID、角色、批准档位与 permit 全部匹配时才允许并原子预占；Required 模式缺少账本路径时会失败关闭。
5. 宿主能够传播 `reservation_id` 时，由 SubagentStart/Stop 自动对账；Codex 0.153.2 未传播时保持 `RESERVED`，不得靠时间顺序猜测。
6. 只有宿主明确证明 Agent 未启动时才能释放预占。Agent 一旦启动，完成、失败或取消都不退款。

示例：

```powershell
python scripts\delegation-budget.py init --ledger C:\safe-state\budget.jsonl --budget-id BUDGET-1 --task-id TASK-1 --project-id PROJECT-1 --repo-fingerprint sha256:<64-hex> --budget-class STANDARD --default-model-profile luna-medium
python scripts\delegation-budget.py decide --ledger C:\safe-state\budget.jsonl --dispatch-key review-data-1 --decision DELEGATE --role reviewer --requested-profile luna-medium --reason-code INDEPENDENT_EVIDENCE_GAIN
```

V7.4.6 不会自动为每个根任务创建账本。统一预算采用任务级显式激活；未设置上述两个环境变量时，Hook 仍执行自动派发档位上限，但不得把该任务记录为“统一预算门禁已通过”。

## 3. 路由原因

允许：`INDEPENDENT_EVIDENCE_GAIN`、`SEMANTIC_COMPLEXITY`、`EVIDENCE_CONFLICT`、`SECURITY_OR_CONCURRENCY_RISK`、`LOWER_TIER_INCONCLUSIVE`、`MISSING_EVIDENCE`、`INLINE_SUFFICIENT`。

- `MISSING_EVIDENCE` 不能用于模型升级。
- `LOWER_TIER_INCONCLUSIVE` 必须引用上一档结果，并且只允许逐级升级。
- Terra High 只允许高风险安全/并发直达，或有上一档结果的逐级升级。
- 未知角色、非法模型组合、非法原因码或损坏账本失败关闭。

## 4. 批准档位、成本与校准

未显式指定模型时按 Task Envelope 默认批准档位计费，依据写为 `policy-default`。每次派发在启动前一次性预占固定单位；启动后不读取、不推断、不保存宿主实际模型身份或推理强度，也不允许据此补扣、退款或改变结果解释。

Reviewer、Explorer、Worker 使用不同收益指标。子 Agent 自报只能形成 pending 样本；主协调 Agent 带 SHA-256 Evidence 引用最终化后，样本才可进入离线回放。离线校准只比较批准档位的结果价值与单位成本；相邻档位样本不足时结果必须为“不调整”。Proposal 永久保持 `execution_authorization=NONE`。

V7.4.2 及更早版本的 Event V2 与 Budget V1 链保持原始字节级验签能力，但新运行时只读打开并投影允许字段，不会把历史模型身份字段带入 V3 事件、Snapshot、Assessment、Proposal 或发布报告；新记录必须写入独立的 V3/V2 链，禁止与旧链混写。

## 5. Codex 0.153.4 边界

V7.4.6 的 Plugin 窗口是 Codex CLI 0.153.4 与此前十个稳定发行版，精确列表由 `config/codex-compatibility-v1.json` 冻结。本地 Marketplace manifest 必须包含 `interface.displayName`；未来版、预发布版和其他窗口外版本不会自动接纳。0.153.4 修复 Astra 在内置模型选择器中的可见性，在未显式配置模型时将其设为内置默认，并把异步提问说明约束为仅在相关工具可用时适用；这些变化不修改本包已冻结的 Plugin/Hook 合同，也不改变自动子 Agent 仅使用 Luna/Terra 档位的策略。

安装完成必须读回 `installed=true`、`enabled=true`、`version=7.4.6`，且 schema 3 宿主快照为 `HOST_COMPATIBLE`。磁盘已有文件不等于 Plugin 已注册或已启用。
