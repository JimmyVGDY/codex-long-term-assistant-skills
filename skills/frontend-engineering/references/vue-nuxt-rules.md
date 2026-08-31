# Vue 与 Nuxt 专项规则

> 仅在实际项目使用 Vue 或 Nuxt 时加载，并与 `frontend-core-rules.md` 共同使用。必须先识别 Vue/Nuxt 和相关插件版本。

## 一、版本和生态识别

确认：

- Vue 2 / Vue 3；
- Options API / Composition API / `<script setup>`；
- Vue Router、Vuex / Pinia；
- Nuxt 版本及 SSR/SSG/Hybrid 模式；
- Vite / Vue CLI / Webpack；
- UI 组件库、宏、自动导入和编译插件。

不得把 Vue 3、Composition API、Pinia 或新版 Router 写法机械套用到 Vue 2 历史项目，也不得为了局部修改全量改写组件风格。

## 二、响应式和组件契约

检查：

- Props 是否被直接修改；
- Emits、Slots、`v-model` 和组件公开契约是否明确；
- `ref`、`reactive`、`toRefs`、解构和响应式丢失；
- `watch` / `watchEffect` 是否产生循环更新、重复请求或未清理副作用；
- `computed` 是否执行异步、写操作或高成本逻辑；
- 组件卸载时定时器、监听器、请求和连接是否清理；
- `provide/inject`、全局属性和事件总线是否形成隐式依赖；
- 动态组件、Teleport、Suspense 和异步组件的状态与错误处理。

## 三、状态、路由和缓存页面

检查：

- Vuex / Pinia 是否区分局部状态、全局状态和服务端状态；
- Store 是否跨账户、跨页面或热更新残留；
- `KeepAlive`、`activated/deactivated` 和路由复用是否留下旧请求或旧状态；
- 路由守卫、动态路由、懒加载和权限路由清理；
- 路由参数变化但组件实例复用时是否重新加载正确数据；
- Store 持久化是否包含敏感或不可序列化内容。

## 四、模板和安全

- `v-html`、动态属性、URL、SVG 和富文本必须受控清洗；
- `v-for` Key 必须稳定，不能使用会变化或冲突的值；
- 条件渲染和列表渲染不得造成意外重复挂载、事件绑定或状态丢失；
- 指令、插件和全局 mixin 应评估副作用与卸载行为。

## 五、Nuxt 与 Hydration

涉及 Nuxt 时检查：

- Server/Client Plugin、Middleware、Composable 和 Runtime Config 边界；
- 仅服务端 Secret 是否泄漏到 public runtime config；
- `useAsyncData` / `useFetch` 等数据键、缓存、去重和刷新策略；
- 请求级状态是否被模块级单例跨账户共享；
- 浏览器 API、随机值、当前时间和本地存储导致的 Hydration mismatch；
- Server Route 里的认证、输入、数据库和业务逻辑是否按后端规则处理。

## 六、Vue 专项复审

- Vue 2/3 与插件版本兼容；
- Props、Emits、Slots、Watch、Computed 和响应式边界；
- Vuex/Pinia、Router、KeepAlive 和动态路由残留；
- 组件卸载、连接、监听器和请求清理；
- Nuxt 服务端/客户端边界和 Hydration；
- `v-html`、动态 URL 和敏感数据；
- 新旧组件、缓存资源和灰度兼容。
