---
name: log-observability-analysis
description: >-
  日志分析、日志文件、故障日志、异常堆栈、应用日志、容器日志、Pod 日志、GC 日志、Nginx 日志、数据库与中间件日志、跨服务时间线或可观测性排障时使用。覆盖本地文件、开发测试、远程非生产和生产只读场景；不因分析日志自动获得修改、清理、重启或生产写权限。
---

# 日志与可观测性分析技能

## 使用范围

用于本地日志文件、上传日志、压缩日志包、应用标准输出、开发/测试/预发布环境日志、远程非生产日志、生产只读日志，以及 Docker、Kubernetes、systemd、Java、Python、数据库、中间件、网关、网络和存储相关日志的结构化分析。

本技能负责横向的日志分析方法、证据组织、时间线关联和排障编排；具体技术机制由 Java、Python 或数据基础设施技能补充，不复制这些领域技能的全部规则。

## 强制执行

1. 开始实质分析前读取 `references/log-observability-analysis-workflow.md`。
2. 先确认日志来源、环境级别、时区、时间窗口、文件范围、编码、格式、敏感信息和允许操作边界。
3. 按环境选择模式：静态文件、本地运行环境、远程非生产只读、生产只读；不得把低风险本地能力自动带入生产环境。
4. 先建立日志清单和时间线，再聚类异常、关联 traceId/requestId/taskId、识别重试/超时/恢复事件，最后形成根因假设。
5. 严格区分已确认、高概率、推测和未验证；日志相关性不能直接写成因果关系。
6. 输出关键证据时只保留最小必要片段并脱敏，不复制完整 Token、Cookie、密钥、身份证、手机号、地址或大段业务数据。
7. 远程和生产只读分析必须限制时间窗、行数、文件范围和命令成本；禁止无限 `tail -f`、无边界递归扫描、Redis `KEYS *`、高消耗全表查询和未经授权的解压/临时写入。
8. 简单单文件任务由主 Agent 分析；仅在跨服务、跨组件、长时间线或多候选根因时，才按来源或维度并行启用只读子 Agent，并由主 Agent 统一归并。
9. 日志分析本身不自动触发代码修改、Git、部署或复审流程；用户明确要求修复后，再组合 `$engineering-quality-delivery` 和对应技术技能。
10. 跨会话或多轮日志收集时组合 `$long-running-task-memory`；需要正式故障报告时组合 `$technical-document-writing`。

## 模式边界

### A. 静态文件分析

可在授权范围内读取、解压、排序、合并和使用临时解析脚本，但必须控制磁盘、内存和临时文件，并保留原始文件不被覆盖。

### B. 本地运行环境分析

可查看本地进程、容器、端口和日志；任何重启、配置修改、清理或数据写入仍需单独授权。

### C. 远程非生产只读分析

默认只读，限制命令成本和扫描范围；不得因为是测试环境就擅自清理、重启或修改数据。

### D. 生产只读分析

仅允许当前任务明确授权的日志、状态、监控和低风险只读查询。禁止修改、删除、清理、部署、重启、扩缩容、切流以及数据库、Redis、MQ、对象存储写操作。

## 与其他技能组合

- Java 堆栈、Spring、JVM、GC、线程、事务：`$java-backend-engineering`
- Python Traceback、协程、Celery、Worker：`$python-backend-ai-engineering`
- MySQL、Redis、RabbitMQ、ES、Docker、K8s、网络和存储：`$data-middleware-ai-infrastructure`
- 长期排障、持续日志观察和检查点：`$long-running-task-memory`
- 正式事故报告、复盘或管理层报告：`$technical-document-writing`
- 从分析进入代码修复、测试、提交或环境写操作：`$engineering-quality-delivery`

## 资产

- 日志分析报告：`assets/templates/LOG_ANALYSIS_REPORT.template.md`
- 时间线：`assets/templates/LOG_TIMELINE.template.md`
- 证据台账：`assets/templates/LOG_EVIDENCE_LEDGER.template.md`

## 核心原则

> 先确定范围和时间，再建立证据链；先区分现象与根因，再提出验证；只读不等于无风险，相关性不等于因果性。
