---
name: java-backend-engineering
description: >-
  Java 后端、Spring Boot、Spring Cloud、Struts2、MyBatis、JPA、Maven、JVM、事务、并发、SSE 或 Java 代码审查任务时使用。先识别 Java 与框架版本；不要用于纯 Python 或纯 Vue 任务。
---

# Java 后端工程技能

## 使用范围

用于 Java 业务后端、传统 Java 老系统、Spring Boot / Spring Cloud、MyBatis / JPA、并发、事务、JVM、SSE、文件和 Java 与 Python 混合服务边界。

## 执行步骤

1. 开始实质分析或修改前，读取 `references/java-backend-rules.md`。
2. 从 `pom.xml`、Gradle、Dockerfile、CI、启动日志和运行环境确认 Java、Spring、Servlet、依赖和构建版本。
3. 阅读目标代码完整上下文、上游调用、下游依赖、配置、数据库和相关测试；不得仅凭局部代码猜测业务。
4. 只使用当前版本支持的语言和 API；Java 8 项目禁止引入 Java 9+ 语法或字节码。
5. 金额使用 `BigDecimal`，明确精度和舍入；普通循环优先传统 `for`，避免难调试的复杂 Stream。
6. 主动检查事务失效、连接池、线程池、幂等、资源释放、序列化兼容、权限、安全和性能高频路径。
7. 修改、测试、复审、提交或交付时，同时使用 `$engineering-quality-delivery`。
8. 涉及数据库、Redis、MQ、搜索、文件、RAG、GPU 或基础设施时，同时使用 `$data-middleware-ai-infrastructure`。

## 边界

- 不把现代 Spring Boot 3.x / Jakarta 写法套入 Java 8、`javax.*` 或 Struts2 老项目。
- 不默认 Java 必须是业务中心，也不默认 Java 项目必须拆微服务。
- 不因技能激活而扩大修改、Git 或环境操作授权。
