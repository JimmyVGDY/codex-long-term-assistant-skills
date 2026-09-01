# Python Web / async / Worker 后端专项索引

> 本索引只补充 Python 运行时、Web、异步与 Worker 专项。模型、RAG、Agent 和 AI 评测由 `$ai-engineering` 负责；只加载当前任务需要的分片。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `python-core-web-frameworks.md` | Python 项目识别、分层与 Web 框架 | Python 版本、FastAPI/Django/Flask、API 分层 |
| `python-concurrency-deployment.md` | 同步异步、GIL、多进程与部署 | Event Loop、线程/进程、CPU 任务、AI SDK 的 Python 运行机制和 Web 部署 |
| `python-data-contract-security.md` | 数据库、迁移、契约、金额、时间、序列化与安全 | ORM/Session、迁移、API 契约、Decimal、认证权限 |
| `python-tasks-quality-testing.md` | Celery、多 Worker、代码质量、依赖和测试 | 任务队列、进程内状态、类型、异常、依赖、测试和代码审查 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 跨域任务可以组合多个分片，但应记录每个分片的唯一职责。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、日志和运行结果始终优先于 Reference 中的通用规则。
