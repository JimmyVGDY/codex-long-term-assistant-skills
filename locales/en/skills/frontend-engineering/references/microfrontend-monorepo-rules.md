# Micro-Frontend and Monorepo Rules

## 1. Boundary Identification

Identify the host application, child applications, shared packages, independent builds, deployment units, route ownership, authentication entry point, shared dependencies, and communication protocols. A monorepo is not inherently a micro-frontend architecture, and multiple packages are not necessarily independently deployable.

## 2. Runtime Isolation

Check isolation of styles, globals, events, routes, Stores, caches, LocalStorage, Cookies, SSE/WebSocket connections, timers, and DOM containers. A child application must clean up all side effects when unmounted.

## 3. Shared Dependencies and Versions

For Module Federation, single-spa, qiankun, and similar systems, validate Shared/Singleton configuration, version ranges, load failures, duplicate framework instances, and staged-rollout compatibility. Changes to shared components and type packages must be evaluated against every consumer.

## 4. Contracts, Release, and Rollback

Define host/child message and API contracts, error isolation, timeouts, degradation, independent releases, asset domains, CSP, caching, monitoring, staged rollout, and rollback. A failed child application must not take down the host.

## 5. Testing

At minimum, validate independent and integrated operation, route transitions, authentication state, unmount/remount, mixed versions, asset-load failure, and rollback. When multiple Agents or teams work concurrently, make directory ownership and integration responsibility explicit.
