# Angular 专项规则

> 仅在实际项目使用 Angular 时加载，并与 `frontend-core-rules.md` 共同使用。先识别 Angular、TypeScript、RxJS、构建器和应用架构版本。

## 一、版本和架构识别

确认：

- Standalone Component 或 NgModule 架构；
- Signals、RxJS、Zone.js 和 Change Detection 模式；
- Router、Reactive Forms / Template Forms；
- SSR/Hydration、构建器、测试工具和 UI 库；
- Service、Provider 和 Dependency Injection 范围。

不得把 Standalone、Signals 或新版模板语法套到旧版本项目，也不得为局部修改强制迁移整个模块体系。

## 二、组件、DI 和变更检测

检查：

- Component、Directive、Pipe、Service 和 Store 职责；
- Provider 范围是否导致意外单例或重复实例；
- Input/Output、双向绑定和不可变数据边界；
- OnPush/默认变更检测、Signals 和手动检测是否正确；
- 生命周期中订阅、监听器和资源是否释放；
- 模板方法、高成本 Pipe 和频繁变更检测；
- ViewChild、动态组件和 Overlay 的生命周期。

## 三、RxJS 和异步

检查：

- 订阅是否通过 `async` pipe、takeUntil 或等价机制释放；
- 高阶映射操作符是否符合取消、顺序和并发语义；
- `shareReplay`、缓存和错误是否造成陈旧数据或泄漏；
- Observable 错误是否被吞掉或导致流永久终止；
- Subject/BehaviorSubject 是否被滥用为全局可变状态；
- HTTP 重试是否考虑幂等和退避。

## 四、路由、表单和拦截器

检查：

- Guard 只改善导航体验，后端仍需权限校验；
- Resolver、懒加载、预加载和路由复用；
- Interceptor 顺序、Token 刷新、重复重试和错误转换；
- Reactive Forms 初值、禁用状态、异步校验和跨字段校验；
- 表单订阅和动态控件是否释放或正确重建。

## 五、Angular SSR 和安全

- 浏览器 API 应受平台边界保护；
- 请求级状态不得跨用户共享；
- TransferState、Hydration 和缓存需考虑用户/租户隔离；
- DomSanitizer 绕过安全必须有明确可信来源；
- 动态模板、URL 和 HTML 不得绕过清洗。

## 六、Angular 专项复审

- Angular/TypeScript/RxJS 版本兼容；
- DI 范围、变更检测、Signals 和组件生命周期；
- RxJS 取消、释放、错误、缓存和并发；
- Router、Guard、Interceptor 和 Forms；
- SSR/Hydration、DomSanitizer 和敏感数据；
- Bundle、懒加载、测试和灰度兼容。
