# Java 项目角色、版本与通用编码规则

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
