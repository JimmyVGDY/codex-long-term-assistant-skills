---
name: python-backend-ai-engineering
description: >-
  Python 后端、FastAPI、Django、Flask、异步 I/O、多进程、Celery、数据处理、模型调用、RAG、GPU Worker 或 Python 代码审查任务时使用。不要默认 Python 仅用于 AI。
---

# Python 后端与 AI 服务技能

## 执行原则

1. 先读取 `references/python-backend-ai-rules.md` 索引，只加载当前问题需要的分片。
2. 从项目配置、锁文件、Dockerfile、CI 和运行环境确认 Python、框架、ORM、驱动、包管理和部署方式。
3. 区分同步 I/O、异步 I/O、CPU 密集和 GPU 密集；`async def` 不等于整条调用链非阻塞。
4. 检查 Event Loop 阻塞、无界并发、协程未等待、Session 生命周期、多 Worker 状态、任务幂等、取消和恢复。
5. 金额使用 `Decimal`，明确时区并避免 naive/aware datetime 混用。
6. 修改运行行为时组合 `$engineering-quality-delivery`；涉及数据/缓存/MQ/RAG/GPU/部署时组合 `$data-middleware-ai-infrastructure`；以 Traceback/Worker/容器日志为主要证据时组合 `$log-observability-analysis`。

## 模型与委派成本

- 文件定位、依赖提取、配置核对和日志分类优先 `luna-low`；明确的数据流、任务状态和普通脚本扫描使用 `luna-medium`。
- 异步调用链、多 Worker 状态、任务恢复和普通 AI 服务判断使用 `terra-medium`；复杂并发、GPU 调度、RAG 权限和不可逆数据处理才使用 `terra-high`。
- 子 Agent 只处理独立只读证据域，不复制模型输入输出、完整日志或父会话历史。

## 边界

- 不默认 Python 只能做 AI，也不因性能问题直接建议重写为 Java。
- 长任务、可靠重试和进程恢复不得只依赖进程内后台 Task。
- Skill 不扩大修改、Git、部署和生产授权。
