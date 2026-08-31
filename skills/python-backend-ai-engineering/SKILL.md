---
name: python-backend-ai-engineering
description: >-
  Python 后端、FastAPI、Django、Flask、异步 I/O、多进程、Celery、数据处理、模型调用、RAG、GPU Worker 或 Python 代码审查任务时使用。不要默认 Python 仅用于 AI。
---

# Python 后端与 AI 服务技能

## 使用范围

用于 Python 完整业务后端、API 服务、异步 Worker、数据处理、文件与视频服务、AI / RAG / GPU 推理服务及 Python 代码审查。

## 执行步骤

1. 开始实质分析或修改前，读取 `references/python-backend-ai-rules.md`。
2. 从 `pyproject.toml`、锁文件、Dockerfile、CI 和运行环境确认 Python、框架、ORM、驱动、包管理和部署方式。
3. 区分同步 I/O、异步 I/O、CPU 密集和 GPU 密集任务；不得因为使用 `async def` 就认定调用链非阻塞。
4. 检查 Event Loop 阻塞、无界并发、协程未等待、Session 生命周期、多 Worker 状态、任务幂等、取消和恢复。
5. 金额使用 `Decimal`，不得使用 `float` 处理金额；时间明确时区并避免 naive / aware 混用。
6. 长任务、可靠重试和进程重启后恢复不得仅依赖 FastAPI `BackgroundTasks` 或进程内 Task。
7. 修改、测试、复审、提交或交付时，同时使用 `$engineering-quality-delivery`。
8. 涉及数据库、Redis、MQ、搜索、文件、RAG、GPU 或部署时，同时使用 `$data-middleware-ai-infrastructure`。

## 边界

- 不默认 Python 只能承担 AI，也不因性能问题直接建议重写为 Java。
- 不把 Web API 的同步处理方式机械套入模型、视频和高资源长任务。
- 不因技能激活而扩大修改、Git 或环境操作授权。
