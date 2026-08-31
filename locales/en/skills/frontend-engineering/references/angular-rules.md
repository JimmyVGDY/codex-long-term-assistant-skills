# Angular-Specific Rules

> Load only when the project uses Angular, together with `frontend-core-rules.md`. Identify Angular, TypeScript, RxJS, builder, and application-architecture versions first.

## 1. Version and Architecture

Confirm:

- standalone components or NgModule architecture;
- Signals, RxJS, Zone.js, and change-detection mode;
- Router and reactive or template-driven forms;
- SSR/hydration, builder, test tools, and UI libraries;
- scope of services, providers, and dependency injection.

Do not apply standalone APIs, Signals, or new template syntax to unsupported versions, and do not migrate the whole module system for a local change.

## 2. Components, DI, and Change Detection

Check:

- responsibilities of components, directives, pipes, services, and stores;
- provider scopes that create unintended singletons or duplicate instances;
- inputs, outputs, two-way binding, and immutable-data boundaries;
- correct use of OnPush or default change detection, Signals, and manual detection;
- release of subscriptions, listeners, and resources across lifecycle hooks;
- template methods, expensive pipes, and excessive change detection;
- ViewChild, dynamic components, and overlay lifecycles.

## 3. RxJS and Asynchrony

Check:

- release through `async` pipe, takeUntil, or equivalent;
- higher-order mapping operators that match cancellation, ordering, and concurrency semantics;
- stale data or leaks from `shareReplay`, caching, and error handling;
- swallowed Observable errors or streams terminated permanently;
- misuse of Subject or BehaviorSubject as global mutable state;
- HTTP retries that account for idempotency and backoff.

## 4. Routing, Forms, and Interceptors

Check:

- guards improve navigation only; the backend still enforces authorization;
- resolvers, lazy loading, preloading, and route reuse;
- interceptor order, token refresh, duplicate retries, and error conversion;
- reactive-form initial values, disabled state, async validation, and cross-field validation;
- correct release or reconstruction of form subscriptions and dynamic controls.

## 5. Angular SSR and Security

- Protect browser APIs behind platform boundaries.
- Do not share request state across accounts.
- Account and tenant isolation must apply to TransferState, hydration, and caches.
- DomSanitizer bypass requires an explicitly trusted source.
- Dynamic templates, URLs, and HTML must not bypass sanitization.

## 6. Angular Review

- Angular, TypeScript, and RxJS compatibility.
- DI scope, change detection, Signals, and component lifecycle.
- RxJS cancellation, release, errors, caching, and concurrency.
- Router, guards, interceptors, and forms.
- SSR/hydration, DomSanitizer, and sensitive data.
- Bundles, lazy loading, testing, and staged compatibility.
