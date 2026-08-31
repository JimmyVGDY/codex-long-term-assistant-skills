# 连接池、并发、任务、集成与流式链路

## 本文件目录

- 九、连接池、线程和并发
- 十、定时任务和批处理
- 十一、Redis、RabbitMQ 和 HTTP 客户端的 Java 特有检查
- 十二、API、金额、时间和序列化
- 十三、文件、SSE 和资源释放

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

现代项目优先 `Instant`、`LocalDate`、`LocalDateTime`、`OffsetDateTime`、`ZonedDateTime` 和 `Duration`。明确系统、数据库、API 和界面显示时区。

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
- 调用方取消是否传递；
- 连接和线程是否泄漏。

---
