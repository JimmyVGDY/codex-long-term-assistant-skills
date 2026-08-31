# V4.1 执行确定性架构

> 历史设计文档：其中预算和流程默认值已被 V4.2 替代；当前规则以 `V4_2_COST_FLOW_OPTIMIZATION.md`、`MODEL_ROUTING_AND_COST_POLICY.md` 和实际脚本为准。


## 目标

在不继续扩大 Skill 数量的前提下，将现有能力从“规则齐全”提升为“调度克制、状态可恢复、证据可失效、子 Agent 上下文隔离、安装可诊断和结果可验证”。

## 核心组件

```text
全局规则：授权、档位、阶段和 Skill 路由
        ↓
领域 Skill：按需加载的技术知识
        ↓
执行信封：目标、权限、阶段、门禁和停止条件
        ↓
execution_guard：仓库指纹和证据有效性
        ↓
独立上下文子 Agent：专业探索和 Reviewer
        ↓
review_packet + review_controller：统一基线、预算和结果
        ↓
长期记忆：跨压缩和跨会话恢复
```

## V4.1 改进

1. 大 Reference 全部分片，按问题域渐进读取；
2. `LIGHT / STANDARD / STRICT` 执行档位；
3. `IDENTIFY → PLAN → IMPLEMENT → VALIDATE → REVIEW → DELIVER` 状态机；
4. 验证和复审证据绑定 Git/差异指纹，变化后自动失效；
5. Reviewer 统一审查包、结构化 Schema 和成本档位；
6. 子 Agent 使用独立上下文，只接收最小任务包并返回摘要；
7. 安装器支持 dry-run、doctor、备份和回滚；
8. 语义校验检查版本、旧名称、Skill 引用、路径和隔离逻辑。
