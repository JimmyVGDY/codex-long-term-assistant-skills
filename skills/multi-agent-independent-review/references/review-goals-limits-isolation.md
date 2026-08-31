# 复审目标、预算与运行时隔离

## 一、目标

多 Agent 复审的目标是独立覆盖关键风险，而不是无上限增加 Reviewer：

> 一次发现、统一归因、集中修复、证据复用、定向复核。

主协调 Agent 负责唯一派发、预算、归并和最终裁决；Reviewer 不修改工作区、不维护共享台账、不继续派生 Agent。

## 二、保守默认预算

```text
MAX_REVIEW_AGENT_DEPTH = 2
MAX_PREIMPLEMENTATION_REVIEW_ROUNDS = 1
MAX_PREIMPLEMENTATION_REVIEWERS = 2
MAX_POST_REVIEW_ROUNDS = 2
MAX_PARALLEL_REVIEWERS = 3
MAX_TOTAL_REVIEW_AGENTS_PER_BOUNDARY = 6
MAX_REPAIR_ROUNDS = 2
MAX_TERRA_HIGH_REVIEWERS = 1
```

含义：

- 深度 0 为主协调 Agent，深度 1 为专业 Reviewer，深度 2 只用于阻塞冲突或定向复核；
- 实施前最多 1 轮、默认 1～2 个 Reviewer；
- 实施后默认最多 2 轮，第一轮最多 3 个、下一轮最多 2 个；
- 单功能边界累计最多 6 个 Reviewer；
- 默认最多 1 个 `terra-high` Reviewer。

为兼容极少数关键任务，控制器保留 V4.1 硬上限：深度 3、实施后 3 轮、并行 6、累计 12、修复 3、`terra-high` 2。放宽必须显式配置并写明风险理由，不能由提示词自动触发。

平台、用户或项目上限更低时采用更低值。不得通过拆分等价调用、重复命名或重建台账规避预算。

## 三、模型预算

自动 Reviewer 只允许 `luna-low / luna-medium / terra-medium / terra-high`。模型路由、升级条件与运行时核验见 `reviewer-model-routing.md`。

模型、人数、上下文、轮次必须同时控制。即使模型不超过 Terra High，多个并行 Reviewer 仍会放大总体消耗。

## 四、运行时隔离

TOML 的 `sandbox_mode = "read-only"` 只是配置意图。必须分别记录父会话实际沙箱、Agent 类型确认、受控探针和最终隔离等级：

| 等级 | 定义 | 可报告内容 |
|---|---|---|
| `system-readonly` | 父会话只读或受控探针明确被沙箱拒绝，且 Agent 类型已确认 | 系统隔离复审 |
| `logical-readonly` | 父会话可写，Reviewer 依靠指令不写 | 逻辑只读复审 |
| `self-review` | 实施 Agent 自查 | 不能替代独立复审 |
| `unknown` | 证据不足 | 未验证 |

生产、真实数据、权限安全、资金、库存和不可逆迁移默认要求 `system-readonly`。可写父会话且无 sandbox denied 证据时，只能报告 `logical-readonly`。

受控写入探针只允许在一次性临时 Git 仓库中运行；禁止在正式项目、生产目录、用户主目录或真实数据目录测试。
