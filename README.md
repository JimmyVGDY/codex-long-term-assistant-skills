# Codex 跨项目长期技术助手 Skills 安装包 v4.0

本包将跨项目工程规则安装为原生 Skills、全局受管规则和专业 Reviewer。v4.0 是破坏性前端能力升级：原 `vue-frontend-engineering` 直接改名并重构为跨框架 `frontend-engineering`。

## v4.0 核心变化

- 通用前端覆盖 Vue/Nuxt、React/Next/Remix、Preact、Angular、Svelte/SvelteKit、Astro/Solid/Qwik/Ember/Web Components、Alpine/HTMX、Ionic/Capacitor、原生 JavaScript、jQuery、Layui 和 JSP；
- 明确 Browser、SSR/Edge、PWA、WebView、Extension、Electron/Tauri Renderer 与主进程/原生桥边界；
- 通用核心、框架专项、安全运行时、质量性能、设计系统/SEO、微前端 Monorepo 分层按需加载；
- 新增只读且有界的 `detect_frontend_stack.py`，综合 package.json、锁文件、Workspace、配置和源码签名生成候选技术栈快照；
- 检测器可识别无 package.json 的静态 HTML/JSP、Fullstack Web、Hybrid Web 和纯 Node.js 后端排除场景；
- 新增技术栈快照、前端审查报告和验证矩阵模板；
- 路由回归覆盖 React、Angular、SvelteKit、Preact、Hybrid Web、微前端、SSR 安全、传统页面、静态站点和桌面主进程排除；
- 安装脚本会备份并移除旧 Vue Skill，不保留兼容别名，避免重复发现和缓存碎片；
- 包校验禁止携带 `__pycache__`/`.pyc` 等本机运行产物。

## Skills

| Skill | 主要用途 |
|---|---|
| `$frontend-engineering` | 跨框架 Web 前端、SSR、Hybrid Web、微前端、传统页面、构建、安全、性能与测试 |
| `$java-backend-engineering` | Java、Spring、MyBatis、事务、并发、JVM |
| `$python-backend-ai-engineering` | Python Web、异步、Celery、AI、RAG、GPU Worker |
| `$data-middleware-ai-infrastructure` | 数据库、Redis、MQ、ES、文件、Docker、K8s |
| `$log-observability-analysis` | Logs、Metrics、Trace、Profiling、告警和变更事件 |
| `$engineering-quality-delivery` | 修改、测试、Git、部署和生产安全 |
| `$multi-agent-independent-review` | 实施前/后多 Reviewer 复审与预算控制 |
| `$technical-document-writing` | 技术方案、架构、接口、部署和正式报告 |
| `$long-running-task-memory` | 跨会话持续检查点与恢复 |

## 前端 Skill 使用

```text
$frontend-engineering

先识别实际技术栈、版本、渲染载体与客户端/服务端边界，再按需读取一个主要框架规则和必要的安全/质量规则。修改运行行为时执行项目实际生产构建与受影响验证。
```

技术栈检测：

```bash
python skills/frontend-engineering/scripts/detect_frontend_stack.py \
  --project-dir /path/to/project \
  --format markdown \
  --max-depth 6 \
  --max-files 2000
```

脚本只读，不安装依赖、不执行项目脚本、不修改项目。输出是有界候选证据，仍需结合配置、入口、源码和运行结果确认。

## 升级

不需要先卸载旧版。解压后在包根目录运行安装脚本；旧 `vue-frontend-engineering` 会先备份再移除。升级后重启客户端并确认技能列表只显示 `frontend-engineering`。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
```

### WSL / Linux

```bash
chmod +x scripts/*.sh
./scripts/install-user.sh
./scripts/verify-user-install.sh
```

## 验证

```bash
python3 scripts/validate-package.py
```

验证覆盖 9 个 Skills、Reviewer、全局受管区块、11 份前端参考规则、3 个模板、12 个检测器自测、路由回归、Shell 安装升级与旧 Skill 清理。PowerShell 实机结果以本机验证脚本为准。

## 迁移提示

- 旧显式调用：`$vue-frontend-engineering`
- 新显式调用：`$frontend-engineering`

详见 `docs/FRONTEND_SKILL_MIGRATION.md` 和 `docs/FRONTEND_SKILL_V4_DESIGN.md`。
