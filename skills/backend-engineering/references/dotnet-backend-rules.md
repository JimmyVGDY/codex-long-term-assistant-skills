# .NET 服务端专项规则

## 版本与宿主

确认 .NET/SDK 目标、`.sln`/`.csproj`、ASP.NET Core、Minimal API、Worker Service、Entity Framework Core、部署模型和 Nullable 设置。不得把旧 .NET Framework、现代 .NET 与不同 ASP.NET 生命周期混为一谈。

## DI、请求与异步

- 检查 Singleton/Scoped/Transient 生命周期，禁止 singleton 捕获 scoped 或请求态对象；
- `HttpContext` 和 scoped DbContext 不得跨请求、后台线程或长期缓存共享；
- async 链路应持续异步，避免 `.Result`、`.Wait()` 和不受控 fire-and-forget；
- 传递 `CancellationToken`，在请求取消、停机和任务超时路径释放资源；
- BackgroundService 处理循环、异常、延迟、停止和作用域创建。

## EF Core、HTTP 与配置

检查 DbContext 生命周期、追踪/非追踪、N+1、Include、并发 Token、事务、迁移和查询物化。使用 HttpClientFactory 或等价生命周期管理，明确超时、重试、熔断和幂等。配置与 Secret 区分环境，Options 校验失败应尽早暴露。

## 安全与验证

检查认证 Scheme、Policy、资源级授权、Anti-forgery、模型绑定、文件上传、Data Protection 和序列化设置。根据项目执行 `dotnet build`、相关测试和分析器；Trim/AOT、Native 库和部署模式变化需单独验证兼容。
