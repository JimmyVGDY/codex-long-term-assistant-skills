# Node.js 与 TypeScript 服务端专项规则

## 版本与运行模式

确认 Node.js 版本、CommonJS/ESM、TypeScript 目标、包管理器和唯一有效锁文件，以及 Express、Fastify、NestJS、Koa、Hapi、Node HTTP、Serverless 或 Worker 运行方式。不得把浏览器全局、DOM API 或前端构建假设带入纯服务端。

## Event Loop 与异步

- 检查同步文件/加密/压缩/序列化、CPU 密集循环和大 JSON 是否阻塞 Event Loop；
- Promise 必须等待或显式收敛，处理 rejection、超时、取消和部分失败；
- `Promise.all`、并发队列、Worker Threads 和 Child Process 必须有界；
- 避免每请求创建连接池、HTTP Agent、SDK Client 或消息连接；
- 检查 AsyncLocalStorage、请求上下文、日志和事务上下文是否跨异步链正确传播。

## 框架与生命周期

Express/Koa 检查中间件顺序、重复 `next`、错误链和响应重复写入；Fastify 检查 Plugin 封装、Hook 顺序、Schema 和生命周期；NestJS 检查 Provider Scope、循环依赖、Guard/Interceptor/Pipe/Filter 职责和 singleton 捕获请求态依赖。

## 数据、任务与资源

Prisma、TypeORM、Sequelize、Knex 和原生驱动检查事务 Client/EntityManager 生命周期、N+1、连接泄漏和迁移兼容。队列 Worker 检查 ACK、幂等、重试、进程信号和优雅停机。Stream、文件、Socket、Timer、Listener 和 AbortController 必须在完成、失败与取消路径清理。

## 质量与安全

检查运行时 Schema 校验，不能用 TypeScript 类型替代外部输入校验。关注原型污染、动态 `require/import`、模板/命令注入、路径穿越、SSRF、ReDoS、供应链脚本和客户端可见环境变量误用。按项目使用测试、类型检查、Lint 和正式构建，不无理由重写锁文件或升级整个工具链。
