# V7.4.0 发行说明

版本：7.4.0  
目标宿主：Codex CLI 0.153.0

## 主要变化

- Reviewer、Explorer、Worker 共用根任务 DelegationBudget V1，模型权重固定为 `1/2/4/8`。
- LIGHT、STANDARD、STRICT 的候选初值分别为 `4/16/32` 加权单位，并同时限制派发、并行、深度与 Terra High 次数。
- PreToolUse 在显式 dispatch permit、稳定宿主派发 ID、角色和模型档位一致时原子预占；账本损坏、未知角色或超额时失败关闭。
- 统一预算按根任务显式激活：宿主同时设置 `CP_DELEGATION_BUDGET_PATH` 与 `CP_DELEGATION_BUDGET_REQUIRED=1`；未激活时只执行模型上限，不宣称预算门禁通过。
- 嵌套 Agent 继续扣根预算。启动后不退款；只有宿主明确证明未启动时才能释放。
- 未显式指定模型时按 Task Envelope 默认档位计费并标记 `policy-default`。普通 Hook 字段不构成可信实际模型证明。
- Reviewer 控制器继续维护轮次、Finding、隔离与停止条件，但统一预算只由 DelegationBudget 计费。
- 三类 Agent 使用不同的收益指标；子 Agent 自报不能自行最终化。离线相邻档位回放不足样本时不调整，所有 Proposal 保持 `execution_authorization=NONE`。
- Codex 0.153.0 的本地 Marketplace manifest 现在生成必需的 `interface.displayName`。

## 兼容边界

V7.4.0 只声明 Codex CLI 0.153.0。“当前稳定版 + 前 10 个稳定版”兼容窗口已明确延后到 V7.4.1，不属于本版完成条件。

## 不变边界

- 自动模型最高仍为 `gpt-5.6-terra + high`。
- 不自动使用 Sol、`xhigh`、`max` 或 `ultra`。
- 不记录 Prompt、回答、代码、Diff、Token 或凭据。
- 预算通过不证明实际模型、任务成功或产出有效。
- Evolution 不自动修改 Skill、Reviewer、预算、路由、AGENTS 或业务代码。
