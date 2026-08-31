# 多 Agent 独立复审自定义 Agent

本目录包含 7 个窄职责 Reviewer。用户级安装脚本会复制到 `${CODEX_HOME:-$HOME/.codex}/agents/`，仓库级安装在显式启用时复制到 `<repo>/.codex/agents/`。

| 文件 | Agent 名称 | 审查维度 |
|---|---|---|
| `cp-review-functional-business.toml` | `cp_review_functional_business` | 功能正确性与业务口径 |
| `cp-review-compatibility-regression.toml` | `cp_review_compatibility_regression` | 原有功能回归与兼容 |
| `cp-review-security-access.toml` | `cp_review_security_access` | 权限与安全 |
| `cp-review-performance-resources.toml` | `cp_review_performance_resources` | 性能与资源负担 |
| `cp-review-data-contract.toml` | `cp_review_data_contract` | 数据与契约一致性 |
| `cp-review-state-concurrency.toml` | `cp_review_state_concurrency` | 状态、并发与交互边界 |
| `cp-review-test-delivery.toml` | `cp_review_test_delivery` | 测试证据与交付边界 |

所有 Reviewer TOML 均声明 `sandbox_mode = "read-only"`，并在行为规则中要求：

- 不修改代码、配置、文档或数据；
- 不提交、推送、部署或重启；
- 不继续派生子 Agent；
- 直接基于实际差异、上下文和证据输出结构化发现。

## 重要运行时边界

TOML 的 `read-only` 只能证明**配置声明**，不能单独证明子 Agent 运行时获得了系统级只读沙箱。实测环境中，父会话为 `danger-full-access` 时，指定 Reviewer 仍可能在可写上下文中运行。

因此必须区分：

- `system-readonly`：父会话实际只读，或有效受控探针明确被沙箱拒绝；
- `logical-readonly`：父会话可写，Reviewer 仅依靠角色约束不写；
- `self-review`：实施 Agent 自查，不能冒充独立复审。

高风险、生产、权限安全、真实数据和不可逆操作的严格复审，应在整体只读父会话中执行。不要仅凭 TOML 声明报告“系统强制只读”。

这些 Reviewer 是叶子 Reviewer。主协调 Agent 负责选择组合、记录隔离等级、等待结果、去重归并、集中修复和后续定向复核。
