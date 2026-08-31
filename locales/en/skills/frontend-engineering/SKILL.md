---
name: frontend-engineering
description: Use for browser, WebView, desktop renderer, JavaScript or TypeScript, web frameworks, state, routing, forms, streaming, build, test, performance, security, SEO, and accessibility work.
---

# Frontend Engineering

1. Identify framework, version, Node version, package manager, lock file, rendering mode, runtime carrier, and client/server boundary before applying framework semantics.
2. Partition monorepos, migrations, and micro-frontends by application boundary. Do not mix Vue, React, Angular, Svelte, or other lifecycle and state semantics.
3. Treat authentication, authorization, XSS, browser storage, files, SSR, streaming, PWA, WebView bridges, desktop renderers, and extensions as explicit security or runtime boundaries.
4. Client validation, disabled controls, menus, and route guards improve experience but cannot replace server-side authorization, idempotency, uniqueness, and business rules.
5. Do not upgrade Node, frameworks, TypeScript, build tools, UI libraries, package managers, or test systems for a local change without evidence.
6. After runtime behavior changes, run the real production build and scope-appropriate type, lint, unit, component, end-to-end, browser, SSR or hydration, mixed-runtime, performance, and interaction checks.
7. Main-process, native mobile, IPC, file, process, updater, and bridge capabilities need additional security review.

Use Luna for bounded discovery, Terra Medium for state and integration reasoning, and Terra High only for SSR or hydration, authorization routing, state races, shared micro-frontend contracts, or high-risk security.
