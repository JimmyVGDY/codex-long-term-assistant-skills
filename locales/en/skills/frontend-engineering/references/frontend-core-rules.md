# Core Frontend Rules

## 1. Project and Runtime Boundaries

Before starting, confirm:

- project type: static site, SPA, MPA, SSR, SSG, ISR, PWA, microfrontend, or hybrid;
- framework, meta-framework, UI library, state management, routing, and data-fetching approach;
- JavaScript or TypeScript, `tsconfig`, Node version, and browser targets;
- npm, pnpm, yarn, or Bun; lock files; workspaces; and install scripts;
- build chain such as Vite, Webpack, Rspack, Rollup, Parcel, esbuild, SWC, or Babel;
- unit, component, E2E, visual-regression, and browser-test tools;
- boundaries among browser, SSR server, build time, Edge, Worker, and BFF code;
- deployment base path, reverse proxy, CDN, caching, and compatibility of old and new assets.

Evidence priority: current task, `package.json`, the single effective lock file, build configuration, entries and routes, source layout, CI/CD, and actual build output. Never infer a framework from a directory name alone.

With multiple lock files, applications, or mixed frameworks, report conflicts and directory boundaries before installing, upgrading, or formatting broadly.

## 2. Component, Module, and State Boundaries

Distinguish page containers, business components, presentation components, shared components, API clients, domain adapters, and pure functions. Distinguish local, URL, cross-component, server, persistent, and derived state.

Proactively check:

- multiple inconsistent state sources or duplicated derived state;
- an unbounded store, context, or service containing everything;
- writes and hidden side effects during render, computed values, getters, or inappropriate lifecycle stages;
- release of requests, timers, listeners, observers, SSE, WebSocket, workers, object URLs, and plugin instances on unmount;
- cross-page, cross-account, or cross-request pollution from global event buses, globals, module singletons, and caches;
- large, sensitive, DOM, connection, or nonserializable objects in persistent state.

Do not add a complex state framework to a simple project for formality. In complex projects, keep data flow directional, traceable, and testable.

## 3. APIs, Asynchrony, Races, and Consistency

Cover normal, loading, empty, error, disabled, partial-success, recovery, offline, and weak-network states. Check:

- timeouts, cancellation, retries, repeated clicks, navigation, and unmount;
- stale responses in search, pagination, autocomplete, autosave, and filtering;
- debounce, throttle, AbortSignal, request sequence, and latest-result validation;
- expired tokens, insufficient authorization, consistent error semantics, and observability;
- field, enum, time, time-zone, money, pagination, sorting, error-code, and version contracts;
- client and server caches, optimistic updates, rollback, and eventual consistency;
- GraphQL, REST, or BFF cache keys, error models, partial data, and retry semantics.

Do not blindly retry non-idempotent operations. Frontend duplicate prevention does not replace backend idempotency. Do not swallow errors, retry forever, repeat dialogs, or create log and telemetry storms.

## 4. Routing and Navigation State

Check route and query parameters, redirect allowlists, page reuse, scroll restoration, unsaved forms, dynamic routes, account switching, and stale authorization caches. URLs must not expose tokens, private data, internal paths, or sensitive query criteria.

## 5. Forms, Lists, and Files

- Forms: initial values, rehydration, dirty state, cross-field and asynchronous validation, money precision, time zones, disabled-during-submit, and failure recovery.
- Lists: empty state, page or cursor, changing totals, stable keys, bulk selection, virtualization, and post-filter state.
- Files: size, type, signature, chunking, resume, progress, cancellation, retries, file-name encoding, download authorization, preview memory, and object-URL release.

Frontend validation of files, money, and fields is an experience layer only; server and storage layers must validate independently.

## 6. Runtime Hosts, Workspaces, and Stack Conflicts

Beyond browsers, detect WebView, PWA, extension, Electron/Tauri renderer, Edge/Worker, and SSR runtimes. The same TypeScript file has different permissions and APIs in a browser, Node, Edge, main process, or native bridge; extension alone does not identify the runtime.

For workspaces and monorepos, record repository root, target application, shared packages, build entry, independent deployment units, and lock-file ownership. Root detection cannot override child projects. Changes to shared UI or type packages must identify every consumer.

When multiple frameworks, lock files, or mixed frontend/backend dependencies exist, define application and runtime boundaries before choosing skills and validation. Do not upgrade or format the whole repository indiscriminately.
