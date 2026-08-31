# Vue and Nuxt-Specific Rules

> Load only when the project uses Vue or Nuxt, together with `frontend-core-rules.md`. Identify Vue, Nuxt, and plugin versions first.

## 1. Version and Ecosystem

Confirm:

- Vue 2 or Vue 3;
- Options API, Composition API, or `<script setup>`;
- Vue Router and Vuex or Pinia;
- Nuxt version and SSR, SSG, or hybrid mode;
- Vite, Vue CLI, or Webpack;
- UI libraries, macros, auto-import, and compiler plugins.

Do not apply Vue 3, Composition API, Pinia, or new Router patterns mechanically to a Vue 2 legacy project, and do not rewrite every component style for a local change.

## 2. Reactivity and Component Contracts

Check:

- direct mutation of props;
- explicit emits, slots, `v-model`, and public component contracts;
- `ref`, `reactive`, `toRefs`, destructuring, and lost reactivity;
- loops, duplicate requests, or uncleaned effects from `watch` and `watchEffect`;
- asynchronous work, writes, or expensive logic inside `computed`;
- cleanup of timers, listeners, requests, and connections on unmount;
- hidden dependencies from provide/inject, global properties, and event buses;
- state and error handling for dynamic components, Teleport, Suspense, and async components.

## 3. State, Routing, and Cached Pages

Check:

- separation of local, global, and server state in Vuex or Pinia;
- store residue across accounts, pages, or hot reload;
- stale requests or state under `KeepAlive`, `activated/deactivated`, and route reuse;
- route guards, dynamic routes, lazy loading, and cleanup of permission routes;
- correct reload when route parameters change but the component instance is reused;
- sensitive or nonserializable data in persisted stores.

## 4. Templates and Security

- Sanitize `v-html`, dynamic attributes, URLs, SVG, and rich text.
- Use stable, noncolliding `v-for` keys.
- Prevent conditional and list rendering from causing repeated mounts, event binding, or state loss.
- Evaluate side effects and teardown for directives, plugins, and global mixins.

## 5. Nuxt and Hydration

Check:

- server/client plugin, middleware, composable, and runtime-config boundaries;
- leakage of server-only secrets into public runtime config;
- data keys, caching, deduplication, and refresh for `useAsyncData` and `useFetch`;
- request state shared across accounts through module singletons;
- hydration mismatches from browser APIs, randomness, current time, or local storage;
- backend-grade handling of authentication, input, databases, and business logic in server routes.

## 6. Vue Review

- Vue 2/3 and plugin compatibility.
- Props, emits, slots, watchers, computed values, and reactivity.
- Vuex/Pinia, Router, KeepAlive, and dynamic-route residue.
- Cleanup of component requests, connections, and listeners.
- Nuxt server/client boundaries and hydration.
- `v-html`, dynamic URLs, and sensitive data.
- Old/new components, cached assets, and staged compatibility.
