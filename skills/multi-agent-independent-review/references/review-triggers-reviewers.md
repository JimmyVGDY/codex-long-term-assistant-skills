# 触发条件、风险分级与 Reviewer 分工

## 一、触发判断

原则上触发：

- 公共 API、共享组件、数据库、缓存、消息、序列化或权限行为变化；
- 核心业务、资金、库存、生产、历史兼容、高并发或一致性链路；
- Worker、调度、脚本、导出和数据处理逻辑的中高风险变化；
- 主 Agent 的最低验证不能覆盖关键风险，或存在独立判断价值。

通常不触发：

- 纯提交拆分、提交信息、标点、排版或无行为变化文档；
- 未修改代码的简短只读分析；
- 单文件、低风险、已有直接测试证明且没有共享契约的小修复；
- 只是为了“多 Agent”形式而重复主 Agent 已完成的等价检查。

## 二、风险与默认规模

| 风险 | 典型场景 | 默认 Reviewer | 默认成本档位 |
|---|---|---:|---|
| 低 | 局部、低频、无共享契约 | 0～1 | `economy` |
| 中 | 单模块业务修改、普通数据库或异步链路 | 1～2 | `balanced` |
| 高 | 跨模块、公共组件、权限、并发、兼容 | 2～3 | `deep` |
| 关键 | 生产、资金、不可逆迁移、核心状态机 | 第一轮 3；后续定向 1～2 | `deep` |

默认不是最低质量标准，而是成本预算。Reviewer 组合应覆盖真正独立的风险维度，不按固定数量凑满。

## 三、专业 Reviewer

| Reviewer | 核心职责 | 常态模型档位 |
|---|---|---|
| `cp_review_functional_business` | 目标问题、业务口径、状态流转、异常和补偿 | `terra-medium` |
| `cp_review_compatibility_regression` | 原有路径、旧接口、旧数据、共享组件和新旧版本共存 | `luna-medium` |
| `cp_review_security_access` | 认证、鉴权、越权、租户、注入、文件和敏感信息 | `terra-medium` |
| `cp_review_performance_resources` | SQL、I/O、连接、线程、队列、内存、Token/GPU 和扩展性 | `luna-medium` |
| `cp_review_data_contract` | 数据库、API、Redis、MQ、序列化和成功边界 | `terra-medium` |
| `cp_review_state_concurrency` | 竞态、幂等、超时、重试、取消、恢复和交互状态 | `terra-medium` |
| `cp_review_test_delivery` | 最低验证、测试缺口、失败项、文档、提交和授权 | `luna-low` |

按 `reviewer-model-routing.md` 的证据条件逐级升级，任何自动 Reviewer 不得超过 `terra-high`。

## 四、职责去重

- 同一问题同时涉及功能与数据时，按根因选择主 Reviewer，另一个只审其独立边界。
- “测试缺失”由测试交付 Reviewer 报告；其他 Reviewer 只在测试缺口直接导致其专业结论无法验证时记录。
- “高频 SQL 导致锁竞争”由性能或数据 Reviewer 选一个主责，状态并发 Reviewer 只补充时序风险。
- 第二意见只用于阻塞冲突，不能作为增加覆盖率的常规方式。
