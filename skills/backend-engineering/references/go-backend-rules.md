# Go 服务端专项规则

## 版本与项目识别

确认 Go 版本、`go.mod`、Workspace、入口、模块边界、生成代码和 Gin、Echo、Fiber、Chi、gRPC 或 `net/http` 运行方式。不得因少量接口强行改造成新框架或引入复杂分层。

## Context、goroutine 与 Channel

- 请求、数据库和下游调用传递 `context.Context`，不得存入长期结构或传 `nil`；
- goroutine 必须有退出条件、取消、错误收敛和生命周期 Owner；
- Channel 明确发送方关闭、容量、背压和阻塞路径，避免重复关闭和永久等待；
- 检查 WaitGroup 配对、锁复制、锁顺序、数据竞争和 loop variable 捕获；
- 使用并发限制，不能为每条数据无界启动 goroutine。

## HTTP、数据与资源

复用带超时与连接池配置的 `http.Client`，处理响应体关闭、上下文取消、重试幂等和大响应上限。数据库检查 `Rows`/`Stmt`/事务关闭、错误路径回滚、连接池总量和 `defer` 位置。文件、压缩流和临时资源必须释放。

## 错误、接口与质量

保留错误链并使用 `errors.Is/As` 判断，不依赖字符串匹配；错误映射不能泄漏内部信息。接口放在真实变化的接缝处，避免为每个结构创建浅接口。修改并发路径应执行相关测试和 race 检查；性能结论需要 benchmark 或运行证据。
