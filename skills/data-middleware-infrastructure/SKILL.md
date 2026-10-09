---
name: data-middleware-infrastructure
description: >-
  数据库、SQL、事务锁、Redis、消息队列、搜索与向量存储、文件/NAS/对象存储、GPU 资源、Docker、Kubernetes、网络或基础设施任务时使用。普通服务端业务、浏览器交互或模型/RAG/Agent 语义任务不要使用。
---

# 数据、中间件与基础设施技能

## 执行原则

1. 先读取 `references/data-middleware-infrastructure-rules.md` 索引，只加载当前组件需要的分片。
2. 确认组件版本、拓扑、数据所有权、契约、容量、环境和运维边界。
3. 数据库检查索引、执行计划、事务锁、DDL、新旧版本共存和回滚；Redis 检查穿透/击穿/雪崩、热点、大 Key、TTL 和锁所有权；MQ 检查确认、ACK、幂等、重试、死信、顺序和堆积。
4. 向量存储和 GPU 资源检查索引/容量、设备/显存、驱动、队列、配额、隔离、监控和恢复；RAG 语义、模型输出、Agent 与 AI 评测组合 `$ai-engineering`。
5. Docker/Kubernetes 检查镜像来源、资源限制、探针、优雅停机、配置密钥、滚动发布和回滚。
6. 以组件日志、Metrics、Trace 或变更事件为主要证据时组合 `$log-observability-analysis`；修改、测试、发布或生产操作时组合 `$engineering-quality-delivery`。

## 模型与委派成本

主 Agent 保持当前选择。子 Agent 的型号、思考强度和预算采用[脚本决策与弹性规则](../multi-agent-independent-review/references/script-first-routing.md)；执行脚本返回的精确参数。

- 新默认覆盖 GPT-6 Luna、Sol、Astra 的 low/medium/high；信息不足采用 Sol/medium，不以缺少理由、收益卡或历史样本阻止派发。
- 模型保留语义判断和调整建议；脚本在既有权限、总预算和允许调整范围内重新计算后才改变调用参数。规模或单次检查失败不直接代表难度，也不必然升档。
- 可计算的读取、去重、计数、预留和重试交脚本。缺证据走默认/降级路径，允许继续与验证通过分开记录。
- 只委派相互独立的只读证据域；同一组件和同一调用链不得被多个子 Agent 从头重复扫描。

## 边界

- 不用增加连接池、拆微服务或引入新中间件掩盖未确认的根因。
- 数据库事务不能覆盖 Redis、MQ、HTTP、对象存储和模型调用。
- 普通应用接口、业务状态、认证和 Worker 机制由 `$backend-engineering` 主导；模型/RAG/Agent 与生成任务语义由 `$ai-engineering` 主导。
- Skill 不扩大生产、数据和基础设施写权限。
