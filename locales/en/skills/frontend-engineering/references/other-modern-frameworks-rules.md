# Other Modern Frameworks, Lightweight Web, and Hybrid Renderer Rules

Load only for the technology actually used and confirm its version from official project configuration. Similar syntax does not justify applying Vue, React, or Angular mechanisms.

## Astro, Solid, Qwik, and Web Components

- Astro: confirm islands, client directives, SSR/SSG, adapters, content collections, and server endpoints; do not leak server secrets into client islands.
- Solid: check fine-grained reactivity, Signal/Memo/Effect dependencies, cleanup, resources, and SSR/hydration; do not apply React Hook rules.
- Qwik: check resumability, serialization boundaries, QRL, loaders/actions, server functions, and deployment adapters.
- Web Components/Lit: check Shadow DOM, attribute/property reflection, custom-element registration, composed/bubbling events, style isolation, and lifecycle.

## Preact

- Confirm React compatibility layer, Signals, Preact Router, and dedicated build plugins.
- Check whether hooks, context, Signals, and component state create multiple sources of truth.
- Do not assume every React ecosystem package supports the current Preact and SSR mode.
- SSR/hydration, islands, and lightweight-bundle gains require runtime evidence.

## Ember

- Confirm Ember/Ember CLI, Octane, Glimmer, Router, Service, and test versions.
- Check tracked state, historical computed patterns, service lifecycle, and route model/controller boundaries.
- Preserve addon, resolver, build-pipeline, and upgrade-path compatibility in legacy projects; do not force a major migration for a local issue.

## Alpine, HTMX, and Hotwire

- Define whether server templates or client state drive the page.
- Check events, component initialization, focus, forms, and history after partial DOM replacement.
- HTMX/Turbo requests still require backend authorization, CSRF, idempotency, and error semantics.
- Protect Alpine global stores, expressions, and dynamic HTML from state pollution and injection.
- Do not mechanically turn a progressively enhanced site into an SPA.

## Ionic, Capacitor, and Hybrid WebView

- Distinguish Web UI, native plugins, bridges, platform permissions, and packaging/signing boundaries.
- Check foreground/background transitions, network recovery, deep links, push, files, camera, location, and permission revocation.
- For WebView storage, cookies, tokens, and caches, consider shared devices, backups, and debug exposure.
- Validate native-plugin inputs, callbacks, and errors; client permissions are not trusted business authorization.
- A passing browser build does not replace device/emulator and target-platform validation.

## Electron and Tauri Renderers

- Review renderer/Web UI with frontend rules. Main processes, Rust, filesystems, processes, updates, and system commands are outside the pure-frontend boundary.
- Check contextIsolation, preload/IPC, command allowlists, CSP, navigation, external links, and local-file exposure.
- Never grant the renderer unbounded Node or system capabilities.
- Updates, signing, protocol handling, and local persistence need separate desktop security and release validation.

## Common Review

- Client, server, native, and main-process boundaries.
- Resource cleanup, state serialization, hydration/resume.
- Bundles, routing, caching, offline behavior, tests, and version compatibility.
- Authorization, bridges/IPC, dynamic HTML, and third-party dependencies.
- For an unlisted framework, use core rules and official configuration; do not invent APIs.
