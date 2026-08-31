# 前端框架与运行载体识别矩阵

优先使用 `scripts/detect_frontend_stack.py` 生成只读、有界候选快照，但脚本结果只是证据之一，仍需结合配置、入口和源码确认。

| 证据 | 候选类型 | 说明 |
|---|---|---|
| `vue` / `nuxt`、`vue.config.*`、`nuxt.config.*`、`.vue` | Vue / Nuxt | 区分 Vue 2/3、Nuxt 版本和 SSR 模式 |
| `react` / `next` / Remix 包、JSX/TSX | React / Next / Remix | 区分 CSR、Pages/App Router、Server/Client 边界 |
| `preact` / `@preact/signals` | Preact | 不机械套用所有 React 行为，确认兼容层和 Signals |
| `@angular/core`、`angular.json` | Angular | 区分 NgModule/Standalone、Signals、RxJS 和 SSR |
| `svelte` / `@sveltejs/kit`、`.svelte` | Svelte / SvelteKit | 区分传统响应式/Runes、Adapter |
| `astro` / `solid-js` / Qwik / `lit` / Ember | 其他现代框架 | 使用专项参考并确认官方配置和版本 |
| Alpine / HTMX / Hotwire | 轻量渐进式 Web | 明确服务端模板、DOM 生命周期和局部增强边界 |
| Ionic / Capacitor | Hybrid WebView | Web UI 使用前端规则，原生桥与系统能力额外审查 |
| Electron / Tauri + 浏览器框架/HTML | 桌面 Renderer | Renderer 可使用前端规则；主进程/Rust/系统命令不属于本技能 |
| `jquery` / `layui` / JSP / HTML 且无现代框架 | 传统或静态前端 | 检查全局变量、加载顺序、服务端模板和浏览器兼容 |
| `single-spa` / `qiankun` / Module Federation | 微前端 | 额外读取微前端规则 |
| Workspace、`pnpm-workspace.yaml`、Nx、Turborepo | Monorepo 候选 | 根目录结论不能自动覆盖每个子项目 |
| 仅 Express/Fastify/Nest/Koa，且无浏览器源码/框架 | Node.js 后端 | 不应激活本 Skill |

## 冲突处理

- 多个锁文件：先确认唯一有效包管理器；
- 多个现代框架：判断 Monorepo、微前端、迁移期还是误残留；
- JSX/TSX 但无框架依赖：结合构建插件、tsconfig 和入口确认；
- 仅 Electron/Tauri 依赖：不能自动认定存在 Renderer 前端；
- 没有 `package.json`：可根据 HTML/JSP/静态资源识别传统前端，但必须降低置信度；
- 检测脚本达到文件/深度上限时：把结果标记为有界快照，不得宣称全仓库扫描完成。
