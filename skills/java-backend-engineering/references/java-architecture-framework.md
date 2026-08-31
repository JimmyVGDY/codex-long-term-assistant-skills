# Java 分层、Spring、事务与持久化

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
