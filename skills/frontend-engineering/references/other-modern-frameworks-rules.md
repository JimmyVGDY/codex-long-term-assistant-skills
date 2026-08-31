# 其他现代框架、轻量 Web 与混合 Renderer 专项规则

仅在实际项目使用对应技术时加载，并结合项目官方配置确认版本。不得因为语法相似就套用 Vue、React 或 Angular 机制。

## Astro、Solid、Qwik 与 Web Components

- Astro：确认 Islands、客户端指令、SSR/SSG、Adapter、内容集合和服务端 Endpoint；避免把服务端 Secret 注入客户端 Island；
- Solid：检查 Fine-grained Reactivity、Signal/Memo/Effect 依赖、Cleanup、资源与 SSR/Hydration；不得套用 React Hook 规则；
- Qwik：检查可恢复性、序列化边界、QRL、Loader/Action、服务端函数和部署 Adapter；
- Web Components / Lit：检查 Shadow DOM、属性/Property 反射、Custom Element 注册、事件 composed/bubbles、样式隔离和生命周期。

## Preact

- 确认是否使用 React 兼容层、Signals、Preact Router 和专属构建插件；
- 检查 Hooks、Context、Signal 与组件状态是否形成多个来源；
- 不假设所有 React 生态包都与当前 Preact 版本和 SSR 模式兼容；
- SSR/Hydration、Island 或轻量 Bundle 优化必须有运行证据。

## Ember

- 确认 Ember/Ember CLI、Octane、Glimmer、Router、Service 和测试体系版本；
- 检查 tracked state、computed 历史写法、Service 生命周期和路由 Model/Controller 边界；
- 修改历史项目时保持 Addon、Resolver、Build Pipeline 和升级路径兼容，不为局部问题强制大版本迁移。

## Alpine、HTMX 与 Hotwire

- 明确页面由服务端模板还是客户端状态驱动；
- 检查局部 DOM 替换后的事件、组件初始化、焦点、表单和历史记录；
- HTMX/Turbo 请求仍需后端权限、CSRF、幂等和错误语义；
- Alpine 全局 Store、表达式和动态 HTML 必须防止状态污染与注入；
- 不把渐进式增强项目机械改造成 SPA。

## Ionic、Capacitor 与 Hybrid WebView

- 区分 Web UI、原生插件、Bridge、平台权限和打包签名边界；
- 检查前后台切换、网络恢复、深链、推送、文件、相机、定位和权限撤销；
- WebView 存储、Cookie、Token 和缓存需考虑设备共享、备份和调试暴露；
- 原生插件输入、回调和错误必须校验，不能把客户端权限视为可信业务授权；
- 浏览器构建通过不能替代真机/模拟器与目标平台验证。

## Electron / Tauri Renderer

- Renderer/Web UI 可按前端规则审查；主进程、Rust、文件系统、进程、更新和系统命令不属于纯前端边界；
- 检查 contextIsolation、preload/IPC、Command allowlist、CSP、导航、外部链接和本地文件暴露；
- 不允许 Renderer 直接获得无边界 Node/System 能力；
- 更新、签名、协议处理和本地持久化需要单独的桌面安全与发布验证。

## 共同复审

- 客户端/服务端/原生/主进程边界；
- 资源清理、状态序列化、Hydration/Resume；
- Bundle、路由、缓存、离线、测试和版本兼容；
- 权限、Bridge/IPC、动态 HTML 和第三方依赖；
- 对未明确覆盖的框架，使用通用核心和官方配置，不编造 API。
