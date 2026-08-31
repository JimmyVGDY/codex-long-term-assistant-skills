# React、Next.js 与 Remix 专项规则

> 仅在实际项目使用 React、Next.js 或 Remix 时加载，并与 `frontend-core-rules.md` 共同使用。先确认 React、元框架、路由和数据层版本。

## 一、版本和运行模式

确认：

- React 和渲染入口；
- Client Component / Server Component 或传统 CSR；
- Next.js Pages Router / App Router，或 Remix Route/Loader/Action；
- 状态管理、服务端状态库、表单和样式方案；
- 构建器、编译器、测试工具和部署运行时。

不得把某个 Next.js 路由模式、Server Component 或 Server Action 写法套到不支持的版本，也不得把纯客户端 React 规则套到服务端代码。

## 二、Hooks、状态和渲染

检查：

- Hook 调用顺序和条件调用；
- `useEffect` / `useLayoutEffect` 依赖、清理和重复执行；
- 闭包陈旧、异步回调读取旧状态和竞态；
- 派生状态、受控/非受控组件和表单状态；
- Context 是否过大导致全树重渲染或隐式依赖；
- `useMemo` / `useCallback` / `memo` 是否有真实收益且依赖正确；
- 列表 Key 是否稳定；
- Ref、DOM、Observer、定时器和订阅是否清理；
- Strict Mode 下副作用是否幂等。

不得为了“性能”机械增加 Memo，也不得在渲染阶段执行副作用或写外部状态。

## 三、异步、错误和服务端状态

检查：

- 请求取消、旧结果覆盖、乐观更新和回滚；
- Suspense、Loading、Error Boundary 和局部失败；
- 服务端状态缓存键、失效、重复请求和用户隔离；
- 事件处理器和异步任务中的异常是否可见；
- 路由切换、组件卸载和并发渲染下状态是否一致。

## 四、Next.js / Remix 服务端边界

检查：

- Server/Client Component 边界和客户端 Bundle 泄漏；
- Route Handler、Server Action、Loader/Action 的认证、授权、输入校验、CSRF 和幂等；
- Cookie、Header、缓存、重验证和动态/静态渲染选择；
- 请求级数据是否被模块级缓存跨用户共享；
- Secret、数据库实体和内部错误是否序列化到客户端；
- Middleware、重定向、并行路由、Streaming 和错误边界；
- Hydration mismatch、浏览器 API 和非确定输出。

承担数据库和核心业务的服务端代码必须组合后端、数据和质量规则。

## 五、React 专项复审

- Hooks 依赖、清理、闭包和 Strict Mode；
- 状态来源、Context、受控组件和 Key；
- 请求竞态、缓存键、乐观更新和错误边界；
- Server/Client 边界、Hydration 和 Secret 泄漏；
- Next/Remix 路由、数据加载和服务端动作安全；
- Bundle、重渲染、内存和新旧版本兼容。
