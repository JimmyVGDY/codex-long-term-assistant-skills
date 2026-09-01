# Node.js and TypeScript Server Rules

Confirm Node, module mode, TypeScript target, package manager, one effective lock file, framework, and process model. Do not import browser globals or frontend build assumptions into a pure server.

- Find synchronous file, crypto, compression, serialization, CPU, and large-JSON work that blocks the event loop.
- Await or explicitly converge Promises. Bound Promise sets, Worker Threads, child processes, and background work; handle rejection, timeout, cancellation, and partial failure.
- Reuse pools, HTTP agents, SDK clients, and messaging connections. Verify AsyncLocalStorage, request, logging, security, and transaction context propagation.
- For Express/Koa, inspect middleware order and error flow. For Fastify, inspect plugin encapsulation, hooks, schemas, and lifecycle. For NestJS, inspect provider scope, cycles, and Guard/Interceptor/Pipe/Filter responsibilities.
- Check Prisma/TypeORM/Sequelize/Knex transaction lifetime, N+1, migrations, and cleanup. Clean streams, files, sockets, timers, listeners, and AbortControllers.
- TypeScript types do not validate external input. Check prototype pollution, dynamic imports, injection, traversal, SSRF, ReDoS, lifecycle scripts, and public environment variables.
