# 多 Agent 独立复审自定义 Agent

本目录包含 7 个窄职责、只读的 Codex 自定义 Reviewer。用户级安装脚本会复制到 `${CODEX_HOME:-$HOME/.codex}/agents/`，仓库级安装在显式启用时复制到 `<repo>/.codex/agents/`。

| 文件 | Agent 名称 | 审查维度 |
|---|---|---|
| `cp-review-functional-business.toml` | `cp_review_functional_business` | 功能正确性与业务口径 |
| `cp-review-compatibility-regression.toml` | `cp_review_compatibility_regression` | 原有功能回归与兼容 |
| `cp-review-security-access.toml` | `cp_review_security_access` | 权限与安全 |
| `cp-review-performance-resources.toml` | `cp_review_performance_resources` | 性能与资源负担 |
| `cp-review-data-contract.toml` | `cp_review_data_contract` | 数据与契约一致性 |
| `cp-review-state-concurrency.toml` | `cp_review_state_concurrency` | 状态、并发与交互边界 |
| `cp-review-test-delivery.toml` | `cp_review_test_delivery` | 测试证据与交付边界 |

所有 Reviewer 均设置 `sandbox_mode = "read-only"`，并被明确要求：

- 不修改代码、配置、文档或数据；
- 不提交、推送、部署或重启；
- 不继续派生子 Agent；
- 直接基于实际差异、上下文和证据输出结构化发现。

它们是叶子 Reviewer。主协调 Agent 负责选择组合、等待结果、去重归并、集中修复和后续定向复核。
