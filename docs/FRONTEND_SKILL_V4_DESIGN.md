# v4.0 通用前端工程 Skill 设计说明

## 目标

将原 `vue-frontend-engineering` 直接改名并扩展为跨框架 `frontend-engineering`，同时控制自动触发、上下文占用、框架语义污染和浏览器/服务端/原生运行边界混淆。

## 主要优化

1. 直接改名，不保留兼容别名，避免重复发现、缓存碎片和双 Skill 竞争；
2. 通用核心与框架专项分层，按需加载；
3. 覆盖 Vue/Nuxt、React/Next/Remix、Preact、Angular、Svelte/SvelteKit、Astro/Solid/Qwik/Ember/Web Components、Alpine/HTMX、Ionic/Capacitor 和传统页面；
4. 明确 Browser、SSR/Edge、WebView、PWA、Extension、Electron/Tauri Renderer 与主进程/原生桥边界；
5. 单独管理安全/运行时、质量/性能、设计系统/SEO、微前端/Monorepo；
6. 新增只读且有界的技术栈检测器，支持 package、配置、Workspace、源码签名、静态 HTML/JSP、混合运行时和纯 Node.js 后端排除；
7. 明确全栈前端框架的服务端逻辑必须按后端标准处理；
8. 新增 Node.js 服务端和 Electron/Tauri 主进程负向路由用例，避免 `package.json` 或桌面依赖导致误触发；
9. 新增技术栈快照、审查报告和验证矩阵模板；
10. 包验证禁止遗留 `__pycache__`/`.pyc`，避免把本机运行产物打入分发包。

## 渐进加载

`SKILL.md` 只保留触发、边界和加载决策；通用核心必读，框架、安全、质量和微前端规则按任务读取。每个独立应用默认只加载一个主要框架专项；多应用仓库先划分目录再分别处理。

## 技术栈检测器边界

检测器：

- 只读，不安装依赖、不执行项目脚本；
- 默认最多扫描 6 层、2000 个文件，并跳过依赖、构建和版本控制目录；
- 输出分类、置信度、框架/版本、Workspace、构建测试工具、渲染候选、源码签名和警告；
- 能识别传统 JSP/HTML 项目以及浏览器+Node 的 Fullstack Web 候选；
- 结果只是候选证据，不能替代实际入口、配置、源码和运行验证。

## 破坏性变更

显式调用从 `vue-frontend-engineering` 改为 `frontend-engineering`。安装脚本会备份并移除旧目录；验证脚本把旧目录残留视为失败。
