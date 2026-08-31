---
name: vue-frontend-engineering
description: >-
  Vue 2、Vue 3、Vite、Vue CLI、Vuex、Pinia、路由、表单、文件上传、SSE、WebSocket、异步竞态、前端性能或 Vue 代码审查任务时使用。不要替代后端权限校验。
---

# Vue 前端工程技能

## 使用范围

用于 Vue 2 / Vue 3 项目、组件设计、状态管理、路由、权限展示、表单、列表、文件、SSE / WebSocket、构建与前端性能。

## 执行步骤

1. 开始实质分析或修改前，读取 `references/vue-frontend-rules.md`。
2. 从 `package.json`、锁文件、构建配置和源码确认 Vue、路由、状态管理、UI 库和构建工具版本。
3. 明确组件、Composable、Store、Router 和 API 层职责，避免状态来源不唯一和隐藏副作用。
4. 检查重复请求、请求竞态、取消、组件卸载清理、路由切换、SSE / WebSocket 生命周期和前后端状态一致性。
5. 前端菜单、按钮和路由守卫仅用于体验，不能替代服务端认证、接口权限和数据权限。
6. 修改前端后至少执行项目正式生产构建，并按改动验证加载、空、错误、禁用、刷新、权限和异常状态。
7. 修改、测试、复审、提交或交付时，同时使用 `$engineering-quality-delivery`。
8. 涉及后端接口、缓存、消息、文件存储或实时链路时，按需组合相应后端或基础设施技能。

## 边界

- 不混用 Vue 2 / Vue 3、Options API / Composition API 或不兼容插件写法。
- 不为局部修改无理由升级 Node、Vue、构建工具或 UI 框架。
- 不因技能激活而扩大修改、Git 或环境操作授权。
