# Java 后端工程规则

> V4.1 将大规则拆为按需 Reference。先读取本索引，只加载当前任务需要的分片；不得为了形式一次读取全部文件。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `java-core-version.md` | Java 项目角色、版本与通用编码规则 | 项目识别、版本兼容、Java 8/17/21 或通用编码任务 |
| `java-architecture-framework.md` | Java 分层、Spring、事务与持久化 | Controller/Service/Repository、Spring、事务、MyBatis/JPA |
| `java-concurrency-integration.md` | 连接池、并发、任务、集成与流式链路 | 线程池、异步、调度、Redis/MQ/HTTP、API/时间/序列化、文件/SSE |
| `java-security-performance-testing.md` | 安全、依赖、微服务、JVM、性能、测试与混合架构 | 安全、依赖、JVM/性能、代码审查、服务拆分或 Java/Python 混合架构 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 跨域任务可以组合多个分片，但应记录每个分片的唯一职责。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、日志和运行结果始终优先于 Reference 中的通用规则。
