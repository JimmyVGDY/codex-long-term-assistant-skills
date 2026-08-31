# React, Next.js, and Remix-Specific Rules

> Load only when the project uses React, Next.js, or Remix, together with `frontend-core-rules.md`. Confirm React, meta-framework, router, and data-layer versions first.

## 1. Version and Runtime Mode

Confirm:

- React version and render entry;
- client/server components or traditional CSR;
- Next.js Pages Router/App Router or Remix routes/loaders/actions;
- state management, server-state library, forms, and styling;
- builder, compiler, tests, and deployment runtime.

Do not use a Next.js router mode, server component, or server action in an unsupported version, and do not apply client-only React rules to server code.

## 2. Hooks, State, and Rendering

Check:

- hook order and conditional calls;
- `useEffect` and `useLayoutEffect` dependencies, cleanup, and repeated execution;
- stale closures, asynchronous callbacks reading old state, and races;
- derived state, controlled/uncontrolled components, and form state;
- oversized contexts causing tree-wide rerenders or hidden dependencies;
- real benefit and correct dependencies for `useMemo`, `useCallback`, and `memo`;
- stable list keys;
- cleanup of refs, DOM, observers, timers, and subscriptions;
- idempotent side effects under Strict Mode.

Do not add memoization mechanically for “performance,” and never perform side effects or external writes during render.

## 3. Asynchrony, Errors, and Server State

Check:

- request cancellation, stale-result overwrite, optimistic updates, and rollback;
- Suspense, loading, error boundaries, and partial failure;
- server-state cache keys, invalidation, duplicate requests, and account isolation;
- visibility of errors in event handlers and asynchronous tasks;
- state consistency under navigation, unmount, and concurrent rendering.

## 4. Next.js and Remix Server Boundaries

Check:

- server/client component boundaries and client-bundle leakage;
- authentication, authorization, input validation, CSRF, and idempotency for route handlers, server actions, loaders, and actions;
- cookies, headers, caching, revalidation, and dynamic/static rendering choices;
- request data shared accidentally through module caches;
- secrets, database entities, or internal errors serialized to clients;
- middleware, redirects, parallel routes, streaming, and error boundaries;
- hydration mismatches, browser APIs, and nondeterministic output.

Server code owning databases or core business logic must also use backend, data, and quality rules.

## 5. React Review

- Hook dependencies, cleanup, closures, and Strict Mode.
- State sources, context, controlled components, and keys.
- Request races, cache keys, optimistic updates, and error boundaries.
- Server/client boundaries, hydration, and secret leakage.
- Next/Remix routing, data loading, and server-action security.
- Bundles, rerenders, memory, and version compatibility.
