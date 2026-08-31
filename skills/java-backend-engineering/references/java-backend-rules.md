# Java 后端工程规则

> 仅在当前任务涉及 Java 项目时加载。本文件补充 Java 特有约束；数据库、Redis、消息队列、文件、AI、生产和 Git 的通用规则由其他模块统一定义。

## 一、项目角色与版本识别

Java 可以承担完整业务系统、单体、模块化单体、微服务、网关、认证权限、订单流程、异步任务、文件元数据、AI 应用业务层、SSE 代理、批处理和传统老系统。

不得因为项目使用 Java 就默认采用 Spring Cloud、DDD、微服务或最新 JDK。

识别顺序：

1. 当前任务明确版本；
2. 项目上下文卡；
3. `pom.xml`、`build.gradle` 和 Wrapper；
4. Dockerfile、CI/CD 和启动脚本；
5. 启动日志和实际运行环境。

需要同时确认：

- Java、Spring Boot、Spring Framework、Spring Cloud 版本；
- Servlet 规范和 `javax.*` / `jakarta.*`；
- 数据访问框架、数据库驱动和构建工具；
- 应用服务器、容器镜像和实际字节码目标。

禁止混用：

- Java 8 与 Java 17/21 专属语法和 API；
- Spring Boot 2.x 与 3.x 配置；
- `javax.*` 与 `jakarta.*`；
- 不兼容的 JDK、插件、框架和驱动版本。

涉及版本差异时必须说明适用版本和兼容风险。

---

## 二、Java 8 与传统项目

Java 8 项目必须使用 Java 8 兼容语法和 API，禁止使用：

- `record`、`sealed class`、模式匹配；
- 文本块、`var`、Switch 表达式；
- 虚拟线程；
- Java 9 以上集合工厂方法和专属 API；
- 高版本字节码。

修改 Java 8、Struts2、旧 Spring、Servlet 或 JSP 项目时，优先保持：

- 现有依赖、Tomcat、Servlet 和 `javax.*` 兼容；
- 公共方法签名、反射调用和 XML 配置；
- JSP、Layui、jQuery 等旧前端调用方式；
- 数据库字段、返回结构、PDF、导出和文件版式；
- 历史业务逻辑、灰度和回滚能力。

除非明确要求，不得为了使用新语法升级整个 JDK、Servlet 命名空间或核心框架。

---

## 三、Java 17 / Java 21

可以合理使用 `record`、Switch 表达式、文本块、模式匹配、密封类和新版日期 API，但必须满足：

- 运行和构建环境明确支持；
- 团队可维护；
- 不破坏序列化、反射、MyBatis、Jackson 和 Spring 兼容；
- 不为了炫技增加理解成本；
- 不因局部优化触发全局升级。

启用虚拟线程前必须评估：

- Spring Boot 和第三方 SDK 支持；
- JDBC 驱动、连接池和下游容量；
- `ThreadLocal`、MDC、SecurityContext 和链路追踪；
- 锁竞争和 CPU 密集任务；
- 是否确实存在大量阻塞 I/O。

虚拟线程不能解决数据库连接不足、慢 SQL、锁竞争、CPU 瓶颈和下游限流。

---

## 四、Java 通用编码规则

- 金额必须使用 `BigDecimal`，禁止 `float` / `double`；
- `BigDecimal` 明确精度和舍入模式，避免 `new BigDecimal(0.1)`；
- 数值比较优先使用 `compareTo`，除非业务要求同时比较 scale；
- 普通循环可以清晰实现时优先传统 `for`，避免复杂嵌套 Stream；
- 避免过度反射、静态全局可变状态、超长方法和超大类；
- 关键业务逻辑添加中文注释并保持项目现有风格；
- 不为追求简短牺牲可读性和可调试性。

主动检查：

- 空指针、集合越界、强制转换和数值溢出；
- 字符编码、时间时区和序列化兼容；
- 资源释放、异常吞噬和日志重复；
- 并发安全、事务边界、数据一致性和权限安全。

---

## 五、分层和对象边界

当 Java 作为业务后端时，保持职责清晰：

- Controller / Endpoint：参数解析、基础校验、接收认证结果、调用服务、统一响应；
- Application / Service：业务编排、规则、状态流转、事务、幂等和数据权限；
- Domain：复杂业务项目中的核心规则和领域对象；
- Repository / DAO / Mapper：数据访问、查询、锁、批量和分页；
- Request / Response / DTO / VO / Entity / PO：按用途隔离；
- Infrastructure / Integration / Client：中间件、文件、远程服务和第三方集成。

禁止：

- Controller 承担复杂业务、长事务、模型推理和大文件任务；
- SQL、Redis 和 MQ 操作散落在 Controller 和工具类；
- 数据库 Entity 无限制暴露给外部接口；
- 简单项目为了形式强行引入复杂 DDD。

---

## 六、Spring Boot 与 Spring MVC

主动检查：

- 参数校验、统一异常和统一响应；
- Filter、Interceptor、AOP 的职责边界；
- Bean 生命周期、循环依赖和初始化副作用；
- Profile、条件装配、配置缺失和默认值；
- 优雅停机、健康检查、请求超时和上传限制；
- CORS、静态资源、接口文档和 Actuator 暴露；
- 配置动态刷新对灰度和回滚的影响。

禁止：

- Controller 中手动管理复杂事务；
- 把静态获取 Spring Bean 作为常规设计；
- Bean 构造阶段执行重型网络或数据库操作；
- 高频 AOP 中进行大量数据库和远程调用；
- 把所有异常统一转换成 HTTP 200；
- 吞掉底层异常导致无法定位。

---

## 七、Spring 事务

涉及 `@Transactional` 时检查：

- 是否经过 Spring 代理、是否同类自调用；
- 方法可见性和异常类型是否触发回滚；
- 捕获异常后是否未重新抛出；
- 传播行为、隔离级别、只读、超时和多数据源；
- 异步方法、消息发送、远程调用和文件 I/O；
- 长事务、锁范围和连接占用。

事务只包围必要的数据库操作，不得在事务中长时间执行：

- HTTP、模型或第三方 SDK 调用；
- 大文件上传下载、FFmpeg 和 NAS 遍历；
- 长时间等待、循环计算和消息消费阻塞。

数据库提交后需要发送消息时，评估事务同步回调、Outbox、本地事务消息、补偿和最终一致性。不得认为数据库事务能覆盖 Redis、MQ、HTTP 和对象存储。

---

## 八、MyBatis、MyBatis-Plus 与 JPA

### 8.1 MyBatis / MyBatis-Plus

检查：

- Mapper 参数、XML 映射、动态 SQL 和空条件；
- `IN` 为空、批量、分页、N+1 和字段映射；
- 类型处理器、枚举、逻辑删除、乐观锁和多租户；
- Wrapper 条件是否重复、遗漏权限或不可审查；
- 分页和排序字段是否有上限和白名单。

优先 `#{}` 参数绑定和明确字段列表。`${}` 只允许受控白名单的动态表名或字段名，禁止直接拼接外部输入。

### 8.2 JPA / Hibernate

检查：

- Entity 生命周期、懒加载、N+1、Fetch 和级联；
- 双向关联、孤儿删除、EntityManager 和脏检查；
- 批量更新、缓存、分页、乐观锁和悲观锁；
- 事务外访问懒加载字段和 JSON 循环引用。

避免 `EAGER` 滥用、无边界实体图、大量级联删除和逐条加载大批量数据。关键业务更新不应只依赖隐式脏检查。

---

## 九、连接池、线程和并发

### 9.1 数据库连接池

检查最大连接数、最小空闲、获取超时、空闲超时、最大生命周期、泄漏检测、数据库上限、多实例总连接、长事务和慢 SQL。

不得单纯增大连接池解决慢查询。增加应用实例时必须重新计算数据库总连接量。

### 9.2 线程和线程池

主动检查共享可变状态、可见性、原子性、锁顺序、死锁、ThreadLocal、MDC、事务和安全上下文传播。

禁止：

- 随意 `new Thread()`；
- 无界线程池和无界队列；
- `Executors.newCachedThreadPool()` 承载不可控任务；
- 在锁内执行远程调用或大文件 I/O。

线程池必须明确核心数、最大数、队列容量、线程名、拒绝策略、空闲时间、超时、监控和优雅关闭。普通请求、数据库、文件、NAS、外部接口、MQ、AI、视频和定时任务应按风险隔离。

### 9.3 `CompletableFuture`

必须显式评估线程池、异常、超时、取消、结果聚合、部分失败和上下文传播。禁止只调用 `runAsync` 或 `supplyAsync` 后忽略线程池和异常。

需要可靠执行、重试和恢复时，优先消息队列或任务系统，而不是仅依赖进程内异步。

---

## 十、定时任务和批处理

涉及 Spring Scheduler、Quartz、XXL-JOB 等时检查：

- 多实例重复执行、分布式锁、Misfire 和任务重叠；
- 幂等、分片、补偿、重试、超时和取消；
- 时区、Cron、手动触发、执行记录和优雅停机。

关键任务记录任务名、调度时间、起止时间、状态、处理数量、成功失败数量、实例和 traceId。

批量任务支持分页或游标、分批提交、限速、失败记录、重试、断点恢复和幂等。

---

## 十一、Redis、RabbitMQ 和 HTTP 客户端的 Java 特有检查

通用可靠性规则见数据中间件模块。本节只补充 Java 客户端和框架特有问题。

### 11.1 Redis 客户端

涉及 RedisTemplate、StringRedisTemplate、Redisson、Lettuce、Jedis 时检查序列化、连接池、超时、线程模型、Pipeline、Lua、锁续期和 Spring 配置隔离。

不得随意修改全局 Redis 序列化器；缓存结构变化必须评估旧数据反序列化。

### 11.2 Spring AMQP

检查 Publisher Confirm / Return、容器 ACK、Prefetch、消费者并发、异常转换、重试拦截器、死信和消息转换器。ACK 时机必须与业务成功边界一致。

### 11.3 HTTP 客户端

涉及 RestTemplate、WebClient、OpenFeign、OkHttp 或 Apache HttpClient 时检查连接、读取、写入超时，连接池、DNS、Keep-Alive、响应大小和资源关闭。

禁止每次请求新建客户端、无超时调用、对非幂等接口盲目重试、在长事务中执行慢调用和记录完整敏感请求响应。

---

## 十二、API、金额、时间和序列化

### 12.1 API 契约

检查字段类型、必填、长度、默认值、枚举、时间格式、金额精度、分页上限、排序白名单、错误码、版本兼容和幂等 Key。

Bean Validation 不能代替权限、状态、跨字段和业务规则校验。

### 12.2 时间

现代项目优先 `Instant`、`LocalDate`、`LocalDateTime`、`OffsetDateTime`、`ZonedDateTime` 和 `Duration`。明确系统、数据库、API 和用户显示时区。

`LocalDateTime` 不包含时区。Java 8 老系统必须共享 `SimpleDateFormat` 时应改为线程隔离或同步保护，通常优先每次创建或 `ThreadLocal` 并确保清理。

### 12.3 JSON

涉及 Jackson、Fastjson 等时检查字段命名、空值、日期、时区、枚举、Long 精度、多态、未知字段、循环引用、敏感字段和反序列化安全。

不得随意修改全局 ObjectMapper。修改序列化行为要评估接口、Redis、MQ、数据库 JSON 和历史数据。旧 Fastjson 需重点关注版本漏洞和 AutoType 风险。

---

## 十三、文件、SSE 和资源释放

### 13.1 文件和流

InputStream、OutputStream、Reader、Writer、JDBC、HTTP Response、ZipFile、临时文件和文件锁必须可靠释放，优先 `try-with-resources`。

检查大文件是否流式处理、大小限制、临时文件清理、编码、路径穿越、覆盖风险和可信文件名。不得无条件加载为完整 byte 数组。

### 13.2 SSE / WebSocket

检查连接生命周期、心跳、超时、客户端断开、服务端取消、异常和完成回调、连接集合清理、线程安全、消息顺序、重复发送、落库、上下文、断线恢复、网关超时、多实例路由和会话粘性。

不能只修复“连接不断开”，还要检查：

- 数据和上下文是否保存；
- 页面刷新后是否恢复；
- 任务状态是否最终一致；
- 用户取消是否传递；
- 连接和线程是否泄漏。

---

## 十四、安全、依赖和微服务

### 14.1 Java 安全

检查认证、接口权限、数据权限、租户隔离、水平和垂直越权、CSRF、CORS、XSS、SQL 注入、命令注入、SSRF、路径穿越、文件上传、反序列化、SpEL / OGNL / 模板注入、XXE、Open Redirect 和日志注入。

权限必须在服务端执行。传统 Struts2 额外关注 OGNL、动态方法调用、文件上传、拦截器和旧版本漏洞。

### 14.2 Maven / Gradle

检查直接和传递依赖、版本冲突、Scope、BOM、插件、JDK 兼容、CVE、License、仓库来源和构建可复现性。

未经明确要求不做大版本升级、不升级无关依赖、不替换核心框架、不修改全局 Maven Settings。

处理冲突时先看依赖树和实际运行版本，再做最小排除并验证兼容。

### 14.3 Spring Cloud

涉及微服务时检查注册发现、配置中心、网关、负载均衡、限流、熔断、降级、超时、重试、链路追踪、灰度、健康检查和优雅下线。

防止多层重试放大、超时不一致、动态刷新状态不一致和同步长调用链。Spring Boot 项目不等于必须使用 Spring Cloud。

---

## 十五、JVM、性能、日志和测试

### 15.1 JVM

分析堆、元空间、直接内存、线程栈、GC、大对象、类加载、ThreadLocal、本地缓存和容器限制。

不能只靠加堆解决问题。结合 GC 日志、Heap Dump、Thread Dump、NMT、JFR、jcmd、jstack 和监控区分堆泄漏、堆外泄漏、线程过多、类加载泄漏和容器限制。

### 15.2 性能

性能问题分别检查 SQL、连接池、Redis、MQ、锁、线程池、GC、序列化、网络、文件 I/O、日志、正则、大对象、集合、算法和第三方 SDK。

尽量建立 QPS、平均耗时、P95/P99、错误率、CPU、内存、GC、线程、队列、连接、SQL 和消息积压基线。没有数据不得宣称优化显著或性能完全无影响。

### 15.3 日志

统一 traceId、requestId、taskId、messageId、operationId、脱敏用户标识、服务和实例、状态、耗时、重试和失败原因。

不吞异常、不重复打印同一堆栈、不在高频循环输出大量 INFO、不打印密码、Token、Cookie、大请求响应、文件内容和完整模型输出。不得长期在生产开启大量 DEBUG 或 SQL 全量日志。

### 15.4 测试

根据修改范围选择 JUnit、Mockito、Spring Boot Test、MockMvc、WebTestClient、Testcontainers、WireMock 和 Awaitility 等。

重点检查测试隔离、数据清理、事务回滚、Mock 边界、外部接口、时间、并发、多次运行和执行顺序。Java 8 老项目遵循现有测试体系，不为少量测试强制升级框架。

全部 Mock 的单元测试不能代替真实集成验证。

---

## 十六、Java 代码审查附加清单

除通用六维复审外，检查：

- `equals` / `hashCode` / `compareTo`；
- 可变集合暴露、静态可变状态和单例线程安全；
- ThreadLocal 泄漏、锁粒度和线程池配置；
- Future 异常、事务失效和连接泄漏；
- 文件流、HTTP 响应和 Stream 资源关闭；
- 反射、泛型擦除、强转、BigDecimal 和时间；
- 序列化、枚举、循环依赖和 Bean 初始化副作用；
- 日志和正则性能、集合容量、批量操作、幂等和重试风暴；
- 临时文件、敏感信息和依赖漏洞。

发现问题时区分语言、框架、数据库、并发、JVM、部署、架构和历史兼容问题，不得简单归因于“Java 慢”或“Spring 有问题”。

---

## 十七、服务拆分和 Java/Python 混合架构

出现性能或维护问题时，不得直接建议拆微服务。先判断是否可通过模块化、SQL、事务、线程池、Worker 隔离、缓存、异步化和部署扩容解决。

拆分依据是业务边界、数据和事务边界、发布独立性、故障隔离、扩缩容、团队和运维成本，而不是技术偏好。

Java 与 Python 混合架构必须明确：

- 统一入口、认证权限和业务主数据归属；
- 事务和业务状态由谁负责；
- AI、媒体和计算任务边界；
- taskId、traceId、幂等 Key 和错误码；
- HTTP、gRPC、MQ 的超时、重试、取消和版本；
- 新旧版本灰度和数据兼容。

避免双方无约束修改同一数据、各自维护不同状态、超时后重复执行和相互同步调用形成循环依赖。
