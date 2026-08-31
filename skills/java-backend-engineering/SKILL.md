---
name: java-backend-engineering
description: >-
  Java 后端、Spring Boot、Spring Cloud、Struts2、MyBatis、JPA、Maven、JVM、事务、并发、SSE 或 Java 代码审查任务时使用。先识别 Java 与框架版本；不要用于纯 Python 或纯前端任务。
---

# Java 后端工程技能

## 执行原则

1. 先读取 `references/java-backend-rules.md` 索引，只加载当前问题需要的分片。
2. 从构建文件、容器、CI、启动日志和运行环境确认 Java、Spring、Servlet/Jakarta、依赖和构建版本。
3. 阅读目标代码完整上下文、调用链、配置、数据和相关测试；不得基于局部代码猜测业务。
4. Java 8 项目禁止 Java 9+ 语法/API；金额使用 `BigDecimal`，普通循环优先清晰的传统 `for`。
5. 主动检查事务失效、连接池、线程池、幂等、资源释放、序列化、权限、安全和高频路径性能。
6. 修改运行行为时组合 `$engineering-quality-delivery`；涉及数据/缓存/MQ/存储/容器时组合 `$data-middleware-ai-infrastructure`；以日志和指标为主要证据时组合 `$log-observability-analysis`。

## 模型与委派成本

- 类、方法、调用位置、配置和受影响文件搜索优先 `luna-low`；范围明确的空值、异常、资源释放和兼容扫描使用 `luna-medium`。
- 业务规则、多文件调用链和普通实现判断使用 `terra-medium`；事务、并发、权限、核心状态机、资金或库存一致性才使用 `terra-high`。
- 主 Agent 已掌握完整上下文时不为简单修改派生子 Agent；探索结果只返回文件、符号、证据和未验证项。

## 边界

- 不把 Boot 3/Jakarta 写法套入 Java 8、`javax.*` 或 Struts2 老项目。
- 不默认 Java 必须是业务中心，也不因激活本技能自动拆微服务。
- Skill 不扩大修改、Git、部署和生产授权。
