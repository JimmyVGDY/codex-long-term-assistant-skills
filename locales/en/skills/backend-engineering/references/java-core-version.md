# Java Project Roles, Versions, and General Coding Rules

## 1. Identify the Project Role and Version

Java may support a complete business system, monolith, modular monolith, microservice, gateway, authentication and authorization, order workflow, asynchronous task, file metadata service, AI application business layer, SSE proxy, batch process, or legacy system.

Do not assume Spring Cloud, DDD, microservices, or the latest JDK merely because a project uses Java.

Identify the environment in this order:

1. Versions explicitly stated by the current task.
2. The project context card.
3. `pom.xml`, `build.gradle`, and build wrappers.
4. Dockerfile, CI/CD configuration, and startup scripts.
5. Startup logs and the actual runtime environment.

Confirm all of the following:

- Java, Spring Boot, Spring Framework, and Spring Cloud versions;
- the Servlet specification and use of `javax.*` or `jakarta.*`;
- data-access framework, database driver, and build tool;
- application server, container image, and actual bytecode target.

Do not mix:

- Java 8 with syntax or APIs exclusive to Java 17 or 21;
- Spring Boot 2.x and 3.x configuration;
- `javax.*` and `jakarta.*`;
- incompatible JDK, plugin, framework, or driver versions.

When a version distinction matters, state the applicable version and compatibility risk.

---

## 2. Java 8 and Legacy Projects

Java 8 projects must use Java 8-compatible syntax and APIs. Do not use:

- records, sealed classes, or pattern matching;
- text blocks, `var`, or switch expressions;
- virtual threads;
- collection factory methods or other APIs introduced after Java 8;
- bytecode targeting a newer Java release.

When modifying Java 8, Struts2, older Spring, Servlet, or JSP projects, preserve:

- compatibility with existing dependencies, Tomcat, Servlet, and `javax.*`;
- public method signatures, reflective calls, and XML configuration;
- legacy frontend call patterns such as JSP, Layui, and jQuery;
- database fields, response structures, PDF output, exports, and file layouts;
- historical business behavior, staged rollout, and rollback capability.

Unless explicitly required, do not upgrade the entire JDK, Servlet namespace, or core framework merely to use newer syntax.

---

## 3. Java 17 and Java 21

Records, switch expressions, text blocks, pattern matching, sealed classes, and modern date APIs may be used when appropriate, provided that:

- the build and runtime environments explicitly support them;
- the result remains maintainable for the team;
- serialization, reflection, MyBatis, Jackson, and Spring compatibility are preserved;
- novelty does not add unnecessary comprehension cost;
- a local optimization does not trigger an unrelated global upgrade.

Before enabling virtual threads, evaluate:

- Spring Boot and third-party SDK support;
- JDBC drivers, connection pools, and downstream capacity;
- `ThreadLocal`, MDC, SecurityContext, and trace propagation;
- lock contention and CPU-bound work;
- whether substantial blocking I/O actually exists.

Virtual threads do not solve insufficient database connections, slow SQL, lock contention, CPU bottlenecks, or downstream rate limits.

---

## 4. General Java Coding Rules

- Use `BigDecimal` for money; never use `float` or `double`.
- Define precision and rounding explicitly, and avoid `new BigDecimal(0.1)`.
- Prefer `compareTo` for numeric comparison unless business rules also require scale equality.
- Prefer a conventional `for` loop when it expresses the logic clearly; avoid deeply nested streams.
- Avoid excessive reflection, global mutable static state, extremely long methods, and oversized classes.
- Add bilingual Chinese-and-English comments to critical business logic while following the repository's established style.
- Do not sacrifice readability or debuggability merely for brevity.

Proactively check:

- null dereferences, collection bounds, unsafe casts, and numeric overflow;
- character encoding, time zones, and serialization compatibility;
- resource release, swallowed exceptions, and duplicate logging;
- concurrency safety, transaction boundaries, data consistency, and authorization.

---
