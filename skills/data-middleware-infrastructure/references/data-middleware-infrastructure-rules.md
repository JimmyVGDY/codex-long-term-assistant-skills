# 数据、中间件与基础设施工程规则

> 先读取本索引，只加载当前任务需要的分片；不得为了形式一次读取全部文件。模型、RAG、Agent 与 AI 评测由 `$ai-engineering` 负责。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `data-contract-database.md` | 数据契约、关系数据库、事务与迁移 | API/数据契约、SQL、索引、事务、锁、DDL 和迁移 |
| `redis-messaging.md` | Redis 与消息队列 | 缓存、分布式锁、RabbitMQ/Celery、ACK、幂等、重试和顺序 |
| `search-storage-streaming.md` | 搜索、向量、文件存储与实时链路 | Elasticsearch/向量库、NAS/对象存储/CDN、SSE/WebSocket |
| `security-observability-runtime.md` | 安全、可观测性、资源预算与运行环境 | 安全/供应链、指标资源、GPU 资源、功能开关、Docker/Kubernetes/网络 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 跨域任务可以组合多个分片，但应记录每个分片的唯一职责。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、日志和运行结果始终优先于 Reference 中的通用规则。
