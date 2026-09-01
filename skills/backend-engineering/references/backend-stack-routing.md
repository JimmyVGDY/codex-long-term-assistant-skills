# 后端技术栈与运行载体识别

## 识别顺序

1. 当前任务指定的应用目录、语言和运行方式；
2. 构建文件、锁文件、工具链与框架配置；
3. 入口、路由、依赖注入、数据访问和任务代码；
4. Dockerfile、Compose、CI、服务单元和启动脚本；
5. 实际运行时、版本命令和启动日志。

## 主要证据

| 技术栈 | 常见证据 | 专项 |
|---|---|---|
| Java / Kotlin JVM | `pom.xml`、Gradle、Spring、Jakarta/Servlet、JAR/WAR | `java-backend-rules.md`；Kotlin 语法另按实际代码处理 |
| Python | `pyproject.toml`、requirements/lock、FastAPI、Django、Flask、Celery | `python-backend-rules.md` |
| Node.js / TypeScript | `package.json`、唯一锁文件、Nest/Fastify/Express/Koa/Hapi | `nodejs-backend-rules.md` |
| Go | `go.mod`、`main`、Gin/Echo/Fiber/Chi、`net/http` | `go-backend-rules.md` |
| .NET | `.sln`、`.csproj`、ASP.NET Core、Worker Service | `dotnet-backend-rules.md` |
| Rust | `Cargo.toml`、Axum/Actix/Rocket/Tonic/Tokio | `rust-other-backend-rules.md` |
| PHP / Ruby / 其他 | Composer/Laravel/Symfony、Bundler/Rails、语言构建文件 | `rust-other-backend-rules.md`，再依据源码确认 |

`package.json` 不等于前端；纯 Node.js API、Worker、CLI daemon 和 Electron 主进程不得因为 JavaScript/TypeScript 自动路由到前端。Next.js、Nuxt、SvelteKit、Remix 等全栈框架先按当前文件和进程判断浏览器还是服务端职责。

## 冲突处理

- Monorepo 先按目录、入口、进程和部署单元分区，不用根目录依赖推断所有子项目。
- 生成代码、SDK、迁移工具和测试夹具不应改变主技术栈判断。
- 同一功能跨多个后端时，先明确业务与数据所有权，再分别加载当前子任务对应专项。
- 无明确证据时只使用通用核心，并在输出中保留版本、框架和运行边界未验证状态。
