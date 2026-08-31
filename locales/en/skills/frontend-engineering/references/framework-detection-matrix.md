# Frontend Framework and Runtime-Host Detection Matrix

Prefer `scripts/detect_frontend_stack.py` for a read-only, bounded candidate snapshot, but treat its output as one evidence source and confirm it against configuration, entry points, and source code.

| Evidence | Candidate Type | Notes |
|---|---|---|
| `vue`, `nuxt`, `vue.config.*`, `nuxt.config.*`, `.vue` | Vue or Nuxt | Distinguish Vue 2/3, Nuxt version, and SSR mode |
| `react`, `next`, Remix packages, JSX or TSX | React, Next, or Remix | Distinguish CSR, Pages/App Router, and server/client boundaries |
| `preact`, `@preact/signals` | Preact | Do not assume every React behavior; confirm compatibility layer and Signals |
| `@angular/core`, `angular.json` | Angular | Distinguish NgModule/Standalone, Signals, RxJS, and SSR |
| `svelte`, `@sveltejs/kit`, `.svelte` | Svelte or SvelteKit | Distinguish legacy reactivity/Runes and adapter |
| `astro`, `solid-js`, Qwik, `lit`, Ember | Other modern framework | Use the specialist reference and confirm official configuration and version |
| Alpine, HTMX, Hotwire | Lightweight progressive web | Define server-template, DOM lifecycle, and partial-enhancement boundaries |
| Ionic, Capacitor | Hybrid WebView | Apply frontend rules to Web UI and separately review native bridge and system capabilities |
| Electron or Tauri plus browser framework/HTML | Desktop renderer | Frontend rules apply to the renderer; main process, Rust, and system commands do not belong to this skill |
| `jquery`, `layui`, JSP, or HTML without a modern framework | Legacy or static frontend | Check globals, load order, server templates, and browser compatibility |
| `single-spa`, `qiankun`, Module Federation | Microfrontend | Also read microfrontend rules |
| Workspace, `pnpm-workspace.yaml`, Nx, Turborepo | Monorepo candidate | Root findings do not automatically apply to every child project |
| Only Express, Fastify, Nest, or Koa without browser source/framework | Node.js backend | Do not activate this skill |

## Conflict Handling

- Multiple lock files: identify the one effective package manager.
- Multiple modern frameworks: determine whether this is a monorepo, microfrontend, migration, or stale residue.
- JSX or TSX without a framework dependency: confirm with build plugins, tsconfig, and entry points.
- Only Electron or Tauri dependency: do not assume a renderer frontend exists.
- No `package.json`: legacy frontend may be inferred from HTML, JSP, and static assets, but lower confidence.
- Detection limit reached: label the result a bounded snapshot, not a complete repository scan.
