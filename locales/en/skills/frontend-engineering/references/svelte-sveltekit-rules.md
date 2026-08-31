# Svelte and SvelteKit-Specific Rules

> Load only when the project uses Svelte or SvelteKit, together with `frontend-core-rules.md`. Identify Svelte version, reactivity mode, Kit routing, and deployment adapter first.

## 1. Version and Reactivity

Confirm:

- Svelte version and legacy reactivity or Runes mode;
- SvelteKit routes, load functions, form actions, hooks, and adapter;
- stores, context, TypeScript, Vite, and test tools.

Do not apply Runes or new SvelteKit APIs to unsupported historical versions.

## 2. Components, Stores, and Lifecycle

Check:

- props, events, snippets/slots, and public component contracts;
- missing or cyclic reactive dependencies;
- store subscriptions, derived stores, and cleanup of manual subscriptions;
- cleanup for `onMount`, actions, listeners, timers, requests, and connections;
- cross-page or cross-request pollution from context and module state;
- repeated mounts or resource residue from DOM work and transitions.

## 3. SvelteKit Server Boundaries

Check:

- server/client boundaries, caching, and dependency invalidation for `load`;
- authentication, authorization, CSRF, input validation, and idempotency for `+server`, form actions, and hooks;
- leakage of private environment variables and serialized data;
- request state shared across accounts through module singletons;
- SSR/hydration, browser APIs, and nondeterministic output;
- adapter compatibility with the deployment runtime.

## 4. Svelte Review

- Version, Runes/legacy reactivity, and Kit APIs.
- Stores, context, subscriptions, and lifecycle cleanup.
- Server security and caching for load, actions, and hooks.
- SSR/hydration and environment-variable boundaries.
- Transition, DOM, bundle, and adapter compatibility.
