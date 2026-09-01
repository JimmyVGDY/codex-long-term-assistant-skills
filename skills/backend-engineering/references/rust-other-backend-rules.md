# Rust 与其他后端技术栈专项规则

## Rust 服务端

确认 Rust Edition、MSRV、Tokio/async-std、Axum/Actix/Rocket/Tonic、Feature 和部署目标。

- 不在 async runtime 中直接执行长时间阻塞 I/O 或 CPU 密集工作；按运行时使用受控 blocking 执行；
- 检查 `Arc` 共享范围、Mutex/RwLock 跨 `.await`、锁顺序、Channel 背压和任务取消；
- 避免生产路径无条件 `unwrap`/`expect`，保留错误来源并稳定映射外部错误；
- 连接池、Stream、临时文件、后台 Task 和 graceful shutdown 必须有明确 Owner；
- `unsafe`、FFI、反序列化和动态加载扩大审查范围。

## PHP、Ruby、Kotlin 与其他服务端

先读取实际构建、框架、入口和部署证据，再将通用核心映射到对应运行时：

- PHP/Laravel/Symfony：请求生命周期、容器 Scope、队列、ORM、长驻 Worker 状态和 Composer 供应链；
- Ruby/Rails：ActiveRecord 查询、事务、Callback、副作用、线程/进程模型、Job 幂等和 Bundler；
- Kotlin/Ktor/JVM：协程 Scope、结构化并发、取消、JVM 版本与 Java 生态兼容；
- 其他运行时：重点确认内存/并发模型、资源生命周期、错误机制、包管理、测试和部署方式。

没有专项证据时不得编造框架能力。只使用 `backend-core-rules.md`，说明未覆盖的语言或框架专属风险，并以当前源码、官方构建配置和运行结果为准。
