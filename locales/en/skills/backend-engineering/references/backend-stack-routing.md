# Backend Stack and Runtime Detection

## Evidence order

1. The application directory, language, and runtime named by the task.
2. Build files, lock files, toolchains, and framework configuration.
3. Entry points, routing, dependency injection, persistence, and job code.
4. Dockerfiles, CI, service definitions, and start scripts.
5. Actual runtime versions and startup logs.

| Stack | Common evidence | Reference |
|---|---|---|
| Java or Kotlin/JVM | Maven/Gradle, Spring, Jakarta/Servlet, JAR/WAR | `java-backend-rules.md` |
| Python | pyproject/requirements/lock, FastAPI, Django, Flask, Celery | `python-backend-rules.md` |
| Node.js or TypeScript | package.json, one lock file, Nest/Fastify/Express/Koa/Hapi | `nodejs-backend-rules.md` |
| Go | go.mod, main, Gin/Echo/Fiber/Chi/net/http | `go-backend-rules.md` |
| .NET | solution/project files, ASP.NET Core, Worker Service | `dotnet-backend-rules.md` |
| Rust | Cargo, Axum/Actix/Rocket/Tonic/Tokio | `rust-other-backend-rules.md` |
| PHP, Ruby, or another stack | Composer/framework, Bundler/Rails, language build files | `rust-other-backend-rules.md` plus source evidence |

A `package.json` does not imply frontend. Pure Node APIs, Workers, daemons, and Electron main processes must not route to frontend merely because they use JavaScript or TypeScript. For full-stack Web frameworks, classify the current file and process as browser or server work.

Split monorepos by directory, process, and deployable. Generated code, SDKs, migration tools, and fixtures do not redefine the primary stack. If evidence remains uncertain, use only the shared core and disclose the unverified runtime and framework details.
