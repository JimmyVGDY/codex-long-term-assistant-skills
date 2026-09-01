---
name: frontend-engineering
description: >-
  Web 前端、浏览器端、WebView 或桌面 Renderer 层任务时使用，包括 JavaScript/TypeScript、HTML/CSS、Vue/Nuxt、React/Next.js/Remix、Preact、Angular、Svelte/SvelteKit、Astro/Solid/Qwik/Ember/Web Components、Alpine/HTMX、Ionic/Capacitor、原生 JavaScript、jQuery/Layui/JSP、SPA/MPA/SSR/SSG/PWA、微前端、组件、状态、路由、表单、文件、SSE/WebSocket、构建、测试、性能、安全、SEO 与可访问性。先识别实际框架、版本、渲染载体和客户端/服务端边界；纯 Node.js 后端、原生移动端、Electron/Tauri 主进程或桌面后端任务不要使用。
---

# 通用前端工程技能

## 定位

用于跨框架 Web 前端、浏览器渲染层、WebView 和桌面 Renderer 工程。核心规则处理浏览器、状态、异步、安全、构建和验证等共性问题；框架、运行载体与高风险专项规则只在识别到对应技术栈后按需加载。

## 最小充分加载

1. 开始实质分析或修改前读取 `references/frontend-core-rules.md`。
2. 优先运行只读脚本：

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/frontend-engineering/scripts/detect_frontend_stack.py" --project-dir <项目目录> --format markdown
   ```

   或手工读取 `package.json`、唯一有效锁文件、Workspace 配置、构建配置、入口文件和源码结构，确认框架、版本、Node、包管理器、渲染模式、运行载体和客户端/服务端边界。检测脚本采用有界扫描，输出只是候选证据，不能替代源码确认。
3. 每个独立应用只读取一个主要框架专项规则；多应用、Monorepo、迁移期或微前端仓库必须先划分目录边界：
   - Vue / Nuxt：`references/vue-nuxt-rules.md`
   - React / Next.js / Remix：`references/react-next-remix-rules.md`
   - Angular：`references/angular-rules.md`
   - Svelte / SvelteKit：`references/svelte-sveltekit-rules.md`
   - Preact、Astro、Solid、Qwik、Ember、Web Components、Alpine/HTMX、Ionic/Capacitor、Electron/Tauri Renderer：`references/other-modern-frameworks-rules.md`
   - 原生 JavaScript、jQuery、Layui、JSP 和传统多页：`references/legacy-frontend-rules.md`
4. 涉及认证、权限、XSS、文件、浏览器存储、SSR、SSE/WebSocket、PWA、WebView/原生桥、桌面 Renderer 或浏览器扩展时，再读取 `references/frontend-security-runtime-rules.md`。
5. 涉及修改、构建、测试、性能、设计系统、SEO、可访问性、国际化、发布或代码审查时，再读取 `references/frontend-quality-performance-rules.md`。
6. 涉及 Workspace、Monorepo、Module Federation、single-spa、qiankun 或多子应用发布时，再读取 `references/microfrontend-monorepo-rules.md`。
7. 不能确认框架时，只使用通用规则并明确假设；不得把 Vue、React、Angular、Svelte、Preact 或其他框架的生命周期、响应式、状态和路由语义互相套用。

## 强制边界

- 前端按钮、菜单、路由守卫、字段校验和防重复只改善体验，不能替代后端认证、数据权限、业务规则、幂等和唯一约束。
- Next.js、Nuxt、SvelteKit、Remix 等全栈框架中的服务端路由、数据库和核心业务逻辑必须组合实际后端、数据和质量技能，不能只按前端规则处理。
- Electron/Tauri 主进程、原生移动代码和 WebView Bridge 属于更高权限边界；Renderer/Web UI 可使用本技能，但系统调用、文件、进程、更新、IPC/Command 和原生能力必须额外进行安全审查。
- 不为局部修改无理由升级 Node、框架、TypeScript、构建工具、UI 库、包管理器或测试体系。
- 不无边界修改锁文件，不执行来源不明的安装脚本，不把客户端可见环境变量当作 Secret。
- 修改前端运行行为后，至少执行项目实际的正式生产构建，并按范围执行类型、Lint、单元/组件/E2E、浏览器、SSR/Hydration、混合运行时或性能验证；构建通过不能替代交互验证。
- 本技能不覆盖纯 Node.js 后端、原生 iOS/Android、Flutter、React Native、Electron/Tauri 主进程或桌面后端；这些任务按实际运行边界加载其他规则。
- 技能激活不能扩大文件修改、Git、部署、生产或数据写入授权。

## 模型与委派成本

- 组件、路由、API、样式和配置定位优先 `luna-low`；明确的空值、Promise、事件解绑、构建证据和兼容扫描使用 `luna-medium`。
- 状态管理、接口联调、多文件交互和普通框架机制判断使用 `terra-medium`；SSR/Hydration、权限路由、状态竞态、微前端公共边界和高风险安全才使用 `terra-high`。
- 技术栈检测结果只作为候选证据；子 Agent 按应用目录和唯一职责分片，不得对同一前端应用重复执行全量依赖与源码扫描。

## 组合关系

- 修改、测试、复审、提交或交付：组合 `engineering-quality-delivery`。
- 服务端接口与业务逻辑：组合 `backend-engineering`；数据库、缓存、消息和对象存储：组合 `data-middleware-infrastructure`；模型、RAG、Agent 与 AI 生成语义：组合 `ai-engineering`。
- 浏览器错误、Source Map、RUM、Trace、性能指标或生产只读排障：组合 `log-observability-analysis`。
- 跨会话、多阶段或多 Agent 前端改造：组合 `long-running-task-memory`。
- 正式前端架构、迁移、设计系统或审查报告：组合 `technical-document-writing`。

## 资产

- 技术栈快照：`assets/templates/FRONTEND_STACK_PROFILE.template.md`
- 前端审查报告：`assets/templates/FRONTEND_REVIEW_REPORT.template.md`
- 验证矩阵：`assets/templates/FRONTEND_VALIDATION_MATRIX.template.md`

## 核心原则

> 先识别框架、版本、渲染模式、运行载体和权限边界，再加载最少必要规则；通用浏览器风险统一检查，框架机制按需加载，客户端体验控制永远不能替代服务端安全和业务正确性。
