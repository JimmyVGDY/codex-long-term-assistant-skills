---
name: backend-engineering
description: >-
  服务端应用、API、业务逻辑、认证鉴权、应用事务、并发、任务、Worker、资源生命周期或后端代码审查时使用，覆盖 Java、Python、Node.js、Go、.NET、Rust 及其他后端技术栈。先识别实际运行时和框架；纯数据库/中间件/基础设施、纯浏览器前端或纯模型/RAG 语义任务不要使用。
---

# 通用后端工程技能

## 定位

用于跨语言服务端应用工程。通用核心处理接口、业务边界、应用事务、状态、并发、任务、安全、资源和验证；语言与框架差异通过专项 Reference 按需加载。

## 最小充分加载

1. 开始实质分析或修改前读取 `references/backend-core-rules.md`。
2. 读取 `references/backend-stack-routing.md`，从构建文件、锁文件、入口、容器、CI 和运行环境确认语言、版本、框架、数据访问、任务系统与部署方式。
3. 每个独立应用默认只读取一个主要技术栈索引：
   - Java / Spring / JVM：`references/java-backend-rules.md`
   - Python Web / async / Worker：`references/python-backend-rules.md`
   - Node.js / TypeScript 服务端：`references/nodejs-backend-rules.md`
   - Go 服务端：`references/go-backend-rules.md`
   - .NET 服务端：`references/dotnet-backend-rules.md`
   - Rust、PHP、Ruby、Kotlin 或其他后端：`references/rust-other-backend-rules.md`
4. 混合后端或 Monorepo 先按目录、进程和部署单元划分边界，只为当前子任务加载对应专项；不得一次加载全部技术栈规则。
5. 无法确认技术栈时只使用通用核心并明确假设和未验证项，不套用某个已知框架的生命周期、事务或并发语义。

## 强制边界

- 后端负责应用成功边界、业务规则、服务端权限、应用事务编排和任务状态；SQL/索引/DDL、Redis/MQ/搜索/存储、GPU 资源、容器和网络机制组合 `$data-middleware-infrastructure`。
- 模型调用契约、结构化输出、Prompt 安全、RAG、Agent、AI 评测和生成任务语义组合 `$ai-engineering`；语言 SDK、Web 接口和 Worker 机制仍由本技能处理。
- 浏览器、WebView 和 Renderer 的状态、路由与交互使用 `$frontend-engineering`；客户端校验不能替代服务端权限、幂等和业务规则。
- 不因性能、维护或语言差异直接建议重写、拆微服务、升级框架或更换技术栈。
- 修改运行行为时组合 `$engineering-quality-delivery`；以日志、Metrics、Trace 或 Profile 为主要证据时组合 `$log-observability-analysis`。
- 技能激活不能扩大文件修改、Git、部署、生产或数据写入授权。

## 模型与委派成本

- 文件、入口、符号、配置和版本定位优先 `luna-low`；明确的空值、异常、资源释放和兼容扫描使用 `luna-medium`。
- 业务规则、多文件调用链、普通并发和任务状态判断使用 `terra-medium`；权限、核心状态机、资金库存、复杂并发和跨服务一致性才使用 `terra-high`。
- 技术栈识别结果只是候选证据；子 Agent 只按独立应用或证据域分片，不重复扫描同一调用链。

## 核心原则

> 先识别运行时、框架、版本、进程和部署边界，再加载最少必要专项；通用服务端风险统一检查，语言机制按需处理，应用事务永远不能覆盖外部系统。
