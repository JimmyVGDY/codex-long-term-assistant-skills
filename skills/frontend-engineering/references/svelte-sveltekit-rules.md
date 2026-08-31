# Svelte 与 SvelteKit 专项规则

> 仅在实际项目使用 Svelte 或 SvelteKit 时加载，并与 `frontend-core-rules.md` 共同使用。先识别 Svelte 版本、响应式模式、Kit 路由和部署适配器。

## 一、版本与响应式

确认：

- Svelte 版本及传统响应式或 Runes 模式；
- SvelteKit 路由、Load、Form Action、Hooks 和 Adapter；
- Stores、Context、TypeScript、Vite 和测试工具。

不得把 Runes 或新版 SvelteKit API 套到不支持的历史版本。

## 二、组件、Store 和生命周期

检查：

- Props、事件、Snippet/Slot 和组件公开契约；
- 响应式依赖是否隐式遗漏或形成循环；
- Store 订阅、派生 Store 和手动订阅是否释放；
- `onMount`、Action、事件监听、定时器、请求和连接的清理；
- Context 和模块级状态是否跨页面或跨请求污染；
- DOM 操作和 Transition 是否造成重复挂载或资源残留。

## 三、SvelteKit 服务端边界

检查：

- `load` 的 server/client 边界、缓存和依赖失效；
- `+server`、Form Action 和 Hooks 的认证、权限、CSRF、输入与幂等；
- `private` 环境变量和序列化数据是否泄漏；
- 请求级状态是否被模块级单例跨账户共享；
- SSR/Hydration、浏览器 API 和非确定输出；
- Adapter 与部署运行时的兼容性。

## 四、Svelte 专项复审

- 版本、Runes/传统响应式和 Kit API；
- Store、Context、订阅和生命周期清理；
- Load/Action/Hook 的服务端安全与缓存；
- SSR/Hydration 和环境变量边界；
- Transition、DOM、Bundle 和部署适配器兼容。
