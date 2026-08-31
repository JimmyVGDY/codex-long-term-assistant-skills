# Frontend Security and Runtime-Boundary Rules

## 1. Authentication, Authorization, and Browser Storage

- Menus, buttons, route guards, and client declarations do not replace server authorization and data permissions.
- Check login, token/session expiry, refresh, revocation, logout, and multi-tab synchronization.
- LocalStorage, SessionStorage, IndexedDB, cookies, URLs, logs, telemetry, and source maps must not leak sensitive information.
- Treat every environment variable included in the client bundle as public.
- After account or tenant switching, clear authorization, caches, routes, and session-scoped data.

## 2. Web Security

Check XSS, DOM XSS, CSRF, CORS, CSP, clickjacking, open redirects, unsafe iframes, postMessage, URL schemes, dynamic scripts, and third-party CDNs. Escape or sanitize HTML, Markdown, rich text, SVG, file names, download links, and external URLs according to context.

Avoid `eval`, string `setTimeout`, uncontrolled `innerHTML`, `document.write`, and executing commands from APIs, logs, or configuration. Evaluate third-party script source, SRI, permissions, privacy, and supply-chain risk.

## 3. SSR, SSG, Hydration, and Edge

- Keep server and client output deterministic and handle hydration mismatches.
- Use browser APIs only inside client boundaries.
- Never share request-specific state across accounts through module or process singletons.
- Do not serialize secrets, database entities, internal errors, or server environment variables to the client.
- Define cache keys, account/tenant isolation, revalidation, invalidation, and CDN Vary dimensions.
- Server actions, route handlers, loaders, actions, middleware, and BFF APIs still require authentication, input validation, CSRF, idempotency, and rate limiting.
- Distinguish API, connection, and dependency compatibility among Edge, Node, and browser runtimes.

## 4. Real-Time Connections, Workers, and PWA

For SSE, WebSocket, polling, BroadcastChannel, web workers, and service workers, check authentication, heartbeat, timeout, backoff reconnection, close, duplicate connections, ordering, disconnect cursors, page unload, browser sleep, multiple tabs, and caller cancellation.

For PWA/service workers, check cache version, update prompts, old assets, offline writes, background sync, push permissions, and old/new frontend-backend compatibility. Keeping a connection open is not enough; prevent resource leaks and state corruption.

## 5. Dependency and Install-Script Security

- Do not run untrusted `curl | sh`, npm postinstall, or scripts outside the repository.
- Evaluate new dependency maintenance, bundle size, license, CVEs, typosquatting, and transitive dependencies.
- Lock files, registries, integrity checks, and package-manager versions should be reproducible.
- Build artifacts, source maps, debug endpoints, and internal API documentation must not be exposed accidentally.

## 6. WebView, Desktop Renderers, and Browser Extensions

- WebView/hybrid: minimize native bridges, deep links, file URIs, debug ports, and platform permissions; treat web, external-link, and native-callback data as untrusted.
- Electron: isolate renderer and Node capabilities; check preload exposure, IPC channels, external navigation, downloads, and updates.
- Tauri: check command/capability allowlists, path and shell arguments, window navigation, and local-resource protocols.
- Browser extensions: check manifest permissions, host permissions, content scripts, messaging, page injection, remote code, and store constraints.
- Main processes, native plugins, and system commands require higher-privilege security, backend, or infrastructure review; frontend checks do not replace it.
