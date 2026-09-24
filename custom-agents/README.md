# 多 Agent 独立复审自定义 Agent

本目录包含 7 个窄职责 Reviewer，安装到 `${CODEX_HOME:-$HOME/.codex}/agents/`。

| 文件 | Agent 名称 | 审查维度 |
|---|---|---|
| `cp-review-functional-business.toml` | `cp_review_functional_business` | 功能正确性与业务口径 |
| `cp-review-compatibility-regression.toml` | `cp_review_compatibility_regression` | 原有功能回归与兼容 |
| `cp-review-security-access.toml` | `cp_review_security_access` | 权限与安全 |
| `cp-review-performance-resources.toml` | `cp_review_performance_resources` | 性能与资源负担 |
| `cp-review-data-contract.toml` | `cp_review_data_contract` | 数据与契约一致性 |
| `cp-review-state-concurrency.toml` | `cp_review_state_concurrency` | 状态、并发与交互边界 |
| `cp-review-test-delivery.toml` | `cp_review_test_delivery` | 测试证据与交付边界 |

Reviewer TOML **有意不配置** `model` 和 `model_reasoning_effort`。主协调者每次显式指定组合，并遵循根任务固定的[模型与成本策略](../docs/MODEL_ROUTING_AND_COST_POLICY.md)：旧 V3 保留冻结评分，显式 V4 先核验场景资格，再比较思考强度或型号切换收益，最后核验预算。职责名称不直接决定型号；登记 Reviewer 上限为 Astra High，自动派发禁止 xhigh/max/ultra。Worker/Explorer 仍使用原四档，上限 Terra High。

所有 Reviewer：

- 先读审查包摘要、差异统计和分配范围，证据不足时再扩大；
- 不修改代码、测试、文档、数据或环境，不提交、推送、部署、重启；
- 不继续派生 Agent；
- 同一根因合并，默认最多 8 组 findings；
- 返回结构化检查范围、证据、未验证项、批准的模型与强度组合及引用、隔离等级；不推断或自报实际宿主模型身份。

## 运行时边界

`sandbox_mode = "read-only"` 只能证明配置意图。父会话可写且没有有效沙箱拒绝证据时，只能报告 `logical-readonly`；高风险、生产、权限安全、真实数据和不可逆操作应在整体只读父会话中执行并验证运行时隔离。
