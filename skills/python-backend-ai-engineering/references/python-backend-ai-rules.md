# Python 后端与 AI 服务工程规则

> 仅在当前任务涉及 Python 时加载。本文件不把 Python 默认限制为 AI 层；数据库、Redis、消息队列、文件、AI、生产和 Git 的通用规则由其他模块统一定义。

## 一、项目角色和版本识别

Python 可以承担完整业务后端、API 服务、微服务、管理后台、AI 模型服务、RAG、异步 Worker、数据处理、文件与视频处理、GPU 推理和自动化脚本。

不得把适用于 AI Worker 的设计套用到普通业务 API，也不得让模型推理和视频长任务沿用同步 Web 请求处理方式。

识别顺序：

1. 当前任务明确版本和框架；
2. 项目上下文卡；
3. `pyproject.toml`、`requirements.txt`、`Pipfile`、`poetry.lock`、`uv.lock`；
4. Dockerfile、CI/CD 和启动脚本；
5. 实际虚拟环境、运行时和启动日志。

需要确认：

- Python 版本和语法目标；
- FastAPI、Django、Flask、Starlette、Sanic、Litestar 等框架；
- 同步或异步数据库驱动；
- Uvicorn、Gunicorn、Hypercorn 等运行方式；
- Celery、Dramatiq、RQ 等任务系统；
- 包管理、类型检查、Lint 和测试体系。

不得编造框架不存在的生命周期、配置或扩展能力。

---

## 二、业务后端分层

当 Python 作为完整业务后端时，优先保持：

- API / Router：请求、参数、认证结果、基础校验和响应；
- Schema / DTO：输入输出和内外模型隔离；
- Application / Service：业务编排、事务、状态、幂等和权限；
- Domain：复杂业务的核心规则；
- Repository / DAO：查询、持久化、锁和批量；
- Model / Entity：持久化模型；
- Infrastructure / Integration：中间件、存储和外部服务。

禁止：

- Router 承担复杂业务、长事务、大量 ORM 和模型长任务；
- ORM 查询散落在 Router、工具类和任务代码中；
- ORM Entity 无限制暴露给外部接口；
- 简单项目强行引入复杂 DDD。

---

## 三、FastAPI 与 Django

### 3.1 FastAPI

主动检查：

- Router、Pydantic Schema、依赖注入和数据库 Session 生命周期；
- 请求模型与响应模型是否分离；
- 异常是否统一收敛；
- 中间件是否重复执行重型操作；
- OpenAPI、CORS、上传大小和敏感接口暴露；
- `async def` 中是否调用阻塞代码；
- 同步和异步数据库驱动是否混用；
- 生命周期资源是否正确初始化和关闭。

`BackgroundTasks` 不应代替可靠任务队列处理长任务、必须重试或恢复的任务、视频处理、模型推理和高资源任务。

### 3.2 Django

主动检查：

- View、Serializer、Service、Model 的职责；
- QuerySet 的 N+1、`select_related` 和 `prefetch_related`；
- 中间件、Signal、Migration、Admin、权限和对象级权限；
- 事务边界、Celery 与 ORM 使用；
- 静态文件和上传文件安全。

不得把复杂核心业务隐藏在 Model `save()`、Signal 或 Serializer 中，避免难以发现的隐式副作用。

---

## 四、同步、异步和阻塞模型

不得因为使用 `async def` 就认定系统具备高并发能力。必须检查完整调用链：

- 数据库和 HTTP 客户端是否异步；
- 文件读写、第三方 SDK 和模型调用是否阻塞；
- 图像、视频、序列化和算法是否 CPU 密集；
- 是否使用同步锁、`time.sleep` 或跨线程异步对象。

在事件循环中直接执行同步数据库、`requests`、大文件同步 I/O、PIL 重计算、FFmpeg 同步等待和 CPU 密集算法可能阻塞所有请求。

处理原则：

- 异步 I/O 使用异步客户端；
- 短阻塞任务放入有界线程池；
- CPU 密集任务使用多进程或独立 Worker；
- 长任务使用可靠任务队列；
- GPU 任务使用独立 GPU Worker。

不得无上限使用 `asyncio.gather`、线程池、进程池和后台 Task。必须设置并发上限、超时、取消、异常收集和资源清理。

---

## 五、多进程、多线程和 GIL

分析性能时区分 I/O 密集、CPU 密集、GPU 密集和混合任务。

### 5.1 I/O 密集

可考虑异步 I/O、受控线程池、多个 Web Worker 和连接池，但必须评估下游容量和多 Worker 连接总量。

### 5.2 CPU 密集

不要依赖单进程多线程获得线性提升。优先多进程、独立计算服务、NumPy、原生库或 C/C++ 扩展。

### 5.3 GPU 密集

检查模型常驻、显存、同卡竞争、Worker 数量、OOM、批处理、任务优先级、多 GPU 分配、取消和恢复。

不得笼统归因于“Python 性能差”，应定位解释器、GIL、数据库、网络、文件 I/O、算法、序列化、SDK、模型、GPU 或服务架构。

---

## 六、Web 服务部署

生产不得只使用开发服务器。根据项目评估 Uvicorn、Gunicorn、Uvicorn Worker、Hypercorn、Nginx、Docker 和 Kubernetes。

检查：

- Worker 数量和单 Worker 内存；
- 请求超时、Keep-Alive、最大请求体和上传限制；
- 优雅关闭、健康和就绪检查；
- 日志、连接池总量和多实例负载均衡。

Worker 数量不能机械套公式，需结合 CPU、内存、请求类型、I/O 比例、连接上限、下游限流和 CPU 密集比例。

多进程下，每个 Worker 通常拥有独立内存、连接池、模型、本地缓存和全局变量。增加 Worker 会同时增加内存和连接数。

---

## 七、数据库、ORM 和迁移

### 7.1 Session 和事务

涉及 SQLAlchemy、Django ORM 等时检查 Session 生命周期、事务、自动提交、自动刷新、懒加载、N+1、批量、连接池、连接泄漏、长事务和锁等待。

数据库 Session 应每个请求或任务独立管理：成功提交、异常回滚、最终关闭，不跨线程、进程和长任务共享。

异步任务不得在入队前创建 Session 再传给 Worker。消息中只传主键、业务标识、不可变参数和对象存储引用，由 Worker 重新加载。

### 7.2 迁移

使用 Alembic 或 Django Migration 等正式工具：

- 已执行历史迁移不得直接修改；
- 新变更使用增量迁移；
- 评估锁表、重建表和新旧应用共存；
- 大数据回填与 DDL 分离；
- 回填支持分批、限速、重试、断点和补偿；
- 生产执行前准备回滚或恢复方案。

修改 ORM Model 不代表数据库已经安全更新。

---

## 八、API、Decimal、时间和序列化

### 8.1 API 契约

检查类型、必填、默认值、长度、枚举、时间时区、分页、响应、错误码、字段兼容和幂等。

Schema 校验不能代替权限、业务规则、状态和数据一致性校验。

### 8.2 金额

金额使用 `Decimal`，禁止 `float`。明确精度、舍入模式、数据库类型和 JSON 序列化方式。

### 8.3 时间

明确数据库、API、系统和用户时区，避免 naive datetime 和 aware datetime 混用。定时任务必须指定业务时区。

### 8.4 序列化

检查 Decimal、datetime、UUID、Enum、ORM 对象、大整数和二进制数据。不得依赖隐式序列化导致接口格式不稳定。

---

## 九、认证、权限和安全

主动检查：

- 密码哈希、Token 有效期、刷新、撤销和 Session；
- CSRF、CORS、Cookie 安全属性和 JWT 算法；
- 接口权限、数据权限、租户隔离和越权；
- SQL 注入、命令注入、SSRF、路径穿越、模板注入和反序列化；
- OpenAPI 和管理接口暴露。

文件上传检查大小、MIME、扩展名、文件签名、随机文件名、存储路径、恶意文件和执行权限。

不得使用明文密码、弱哈希和不受控的反序列化。

---

## 十、Celery 与异步任务

涉及 Celery 时检查 Broker、Result Backend、Serializer、ACK、`acks_late`、Worker 丢失、Prefetch、重试、指数退避、Soft/Hard Time Limit、幂等、取消、恢复和定时任务重复。

关键任务不能只依赖 Celery Task ID 作为业务状态。应有业务任务表记录：

- 业务任务 ID、类型、状态、阶段和进度；
- 幂等 Key、重试次数、失败原因；
- 创建、开始、完成时间和取消标记；
- traceId、输入引用和输出引用。

重试必须区分可重试、不可重试、参数错误、业务拒绝、临时下游故障、数据库冲突和资源不足。禁止无差别无限重试。

---

## 十一、本地状态与多 Worker

多 Worker 或多实例环境中，进程内变量不是全局共享状态。

用户 Session、分布式任务状态、全局锁、限流计数、幂等记录、业务状态和多实例共享缓存不得只存在进程内。

进程内缓存只适用于可丢失、可重建、不要求实例一致、有大小上限和 TTL 的数据。必须评估多 Worker 内存倍增和状态不一致。

---

## 十二、类型、异常和代码质量

生产代码尽量使用类型标注、明确返回类型和数据模型。根据项目使用 mypy、pyright、Ruff、Black 和 isort，不得为了通过检查大量使用 `Any`、无意义 `cast` 和全局忽略。

禁止吞异常：

```python
try:
    ...
except Exception:
    pass
```

捕获后应根据场景记录上下文、转换业务异常、回滚、清理、判断重试并继续抛出。

主动检查：

- 可变默认参数、全局可变状态和深浅拷贝；
- 上下文管理器、文件和连接释放；
- 协程未等待、后台 Task 异常丢失和事件循环阻塞；
- 跨线程或跨进程共享对象；
- 导入时副作用、循环依赖、内存增长和临时文件；
- 不受控并发和任务泄漏。

---

## 十三、依赖和测试

### 13.1 依赖

明确使用 requirements、Poetry、uv 或 Pipenv，并尽量锁定版本。检查 Python 范围、传递依赖、平台和 C 扩展、CUDA、CVE、License 和镜像兼容。

未经明确要求不做大版本升级、不升级无关依赖、不在生产直接执行未经审查的 `pip install -U`。

### 13.2 测试

根据修改范围选择 pytest、pytest-asyncio、HTTPX、Django TestCase、Factory Boy 和 Testcontainers。

重点检查 Fixture 隔离、数据库清理、时间、随机数据、外部服务 Mock、异步任务是否真正执行、执行顺序和多次运行稳定性。

全部 Mock 的单元测试不能代替集成验证。

---

## 十四、Python 代码审查附加清单

除通用六维复审外，检查：

- 可变默认参数和全局状态；
- 协程、Task、Event Loop 和取消；
- 多 Worker 状态、连接和内存倍增；
- ORM Session、事务和连接泄漏；
- Decimal、时区和序列化；
- 文件、临时文件和上下文管理器；
- 导入副作用、循环依赖和异常吞噬；
- 并发上限、超时、重试和任务恢复。

发现问题时区分语言、框架、数据库、并发模型、架构和部署问题，不得简单归因于 Python 本身。
