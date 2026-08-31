---
name: data-middleware-ai-infrastructure
description: >-
  MySQL、PostgreSQL、SQL、事务锁、Redis、RabbitMQ、Elasticsearch、向量检索、NAS、对象存储、GPU 资源、Docker、Kubernetes、网络或基础设施任务时使用。纯 Python 应用、模型调用代码和业务 Worker 优先使用 Python Skill。
---

# 数据、中间件、AI 与基础设施技能

## 使用范围

用于数据库、SQL、Redis、消息队列、Elasticsearch、向量检索、文件与对象存储、SSE / WebSocket、RAG 检索基础设施、GPU 资源、Docker、Kubernetes、网络和基础设施。Python 应用代码、模型调用和 Worker 实现由 Python Skill 主导。

## 执行步骤

1. 开始实质分析或修改前，读取 `references/data-middleware-ai-infrastructure-rules.md`。
2. 先识别当前组件、版本、拓扑、数据所有权、契约、容量、生产状态和运维边界。
3. 数据库检查索引、执行计划、事务、锁、DDL、新旧代码共存和回滚；生产写入必须单独授权。
4. Redis 检查穿透、击穿、雪崩、热点、大 Key、TTL、锁所有权和集群切换；禁止无授权清理生产数据。
5. MQ 检查生产确认、ACK、幂等、重试、死信、顺序、堆积和 Poison Message；明确业务成功边界。
6. AI / RAG / GPU 检查输出校验、注入、超时、降级、检索权限、资源队列、显存、取消和失败恢复。
7. Docker / Kubernetes 检查镜像来源、资源限制、探针、优雅停机、配置和密钥、滚动发布与回滚。
8. 任务以数据库、中间件、容器、Kubernetes、网络或存储日志为主要证据时，同时使用 `$log-observability-analysis`。
9. 修改、测试、复审、提交、发布或生产操作时，同时使用 `$engineering-quality-delivery`。

## 边界

- 不因为项目存在性能问题就直接增加连接池、拆微服务或引入新中间件。
- 不把数据库事务误认为能覆盖 Redis、MQ、HTTP、对象存储和模型调用。
- 不因技能激活而扩大生产、数据或基础设施写操作授权。
