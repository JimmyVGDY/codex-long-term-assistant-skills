# 前端安全与运行时边界规则

## 一、认证、权限与浏览器存储

- 菜单、按钮、路由守卫和客户端声明不能代替服务端鉴权与数据权限；
- 检查登录、Token/Session 过期、刷新、撤销、退出和多标签页同步；
- LocalStorage、SessionStorage、IndexedDB、Cookie、URL、日志、埋点和 Source Map 不得泄漏敏感信息；
- 会进入客户端 Bundle 的环境变量一律视为公开信息；
- 账号或租户切换后清理权限、缓存、路由和用户态数据。

## 二、Web 安全

检查 XSS、DOM XSS、CSRF、CORS、CSP、点击劫持、Open Redirect、不安全 iframe、postMessage、URL Scheme、动态脚本和第三方 CDN。HTML、Markdown、富文本、SVG、文件名、下载链接和外部 URL 必须按上下文转义或清洗。

避免 `eval`、字符串 `setTimeout`、不受控 `innerHTML`、`document.write` 和执行接口、日志或配置中的命令。第三方脚本评估来源、SRI、权限、隐私和供应链风险。

## 三、SSR、SSG、Hydration 与 Edge

- 服务端与客户端输出应确定一致，处理 Hydration mismatch；
- 浏览器 API 只能在客户端边界使用；
- 请求级状态不得被模块级或进程级单例跨用户共享；
- Secret、数据库实体、内部错误和服务端环境变量不得序列化到客户端；
- 缓存键、用户/租户隔离、重验证、失效和 CDN Vary 维度必须明确；
- Server Action、Route Handler、Loader、Action、Middleware 和 BFF 接口仍需认证、输入校验、CSRF、幂等和限流；
- Edge Runtime、Node Runtime 和浏览器 Runtime 的 API、连接和依赖兼容必须区分。

## 四、实时连接、Worker 与 PWA

SSE、WebSocket、轮询、BroadcastChannel、Web Worker 和 Service Worker 检查：认证、心跳、超时、退避重连、关闭、重复连接、消息顺序、断线游标、页面卸载、浏览器休眠、多标签页和用户取消。

PWA/Service Worker 需检查缓存版本、更新提示、旧资源、离线写入、后台同步、Push 权限和新旧前后端兼容。不能只确保“连接不断开”，还要避免资源泄漏和状态错乱。

## 五、依赖与安装脚本安全

- 不运行来源不明的 `curl | sh`、npm postinstall 或仓库外脚本；
- 新依赖评估维护状态、包体积、License、CVE、拼写仿冒和传递依赖；
- 锁文件、Registry、完整性校验和包管理器版本应可复现；
- 构建产物、Source Map、调试入口和内部 API 文档不得无意暴露。
## 六、WebView、桌面 Renderer 与浏览器扩展

- WebView/Hybrid：原生 Bridge、深链、文件 URI、调试端口和平台权限必须最小化；来自网页、外链和原生回调的数据均视为不可信输入；
- Electron：优先隔离 Renderer 与 Node 能力，检查 preload 暴露面、IPC 通道、外部导航、下载和自动更新；
- Tauri：检查 Command/Capability allowlist、路径与 Shell 参数、窗口导航和本地资源协议；
- 浏览器扩展：检查 Manifest 权限、Host Permission、Content Script、消息通道、页面注入、远程代码和商店发布要求；
- 上述载体的主进程、原生插件和系统命令需要组合更高权限的安全、后端或基础设施审查，不能由前端检查替代。
