# Python 项目识别、分层与 Web 框架

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
