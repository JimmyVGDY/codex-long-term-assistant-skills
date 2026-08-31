# Frontend Quality, Performance, and Delivery Rules

## 1. Performance and Resources

Check repeated renders, deep comparisons, large-object copying, long main-thread tasks, forced synchronous layout, layout thrashing, large lists, image/video, canvas, editors, preview resources, detached DOM, listeners, object URLs, cache growth, duplicate requests, excessive prefetching, and third-party scripts.

Evaluate route splitting, lazy loading, tree shaking, duplicate bundle dependencies, compression, image formats, fonts, and caching. Use web workers, virtual lists, memoization, caches, and preloading only for measured bottlenecks.

Base performance claims on build analysis, Core Web Vitals, RUM, browser Performance/Memory, Lighthouse, or reproducible comparisons—not intuition from source code.

## 2. Styling, Accessibility, and Internationalization

Check responsive layout, touch, zoom, high DPI, dark mode, print, CSS scope, cascade conflicts, and overflow. Check semantic HTML, keyboard use, focus, ARIA, contrast, screen readers, and notification of dynamic content.

Internationalization checks include text expansion, plurals, RTL, numbers, money, dates, time zones, daylight saving time, and server/client formatting consistency. One screenshot does not prove acceptance.

## 3. Build, Environment, and Release

- Distinguish build-time and runtime variables.
- Check API base URL, proxy, base path, history fallback, content hashes, CDN, cache headers, and source maps.
- Check development versus production differences, workspace or monorepo build caches, and shared-package versions.
- During rollout, validate compatibility among old/new frontend, backend APIs, service workers, and static assets.
- Do not change global npm configuration, package manager, lock file, or major dependency versions without reason and authorization.

## 4. Testing and Minimum Validation

After changing frontend runtime behavior, run the project's real production build at minimum. Select according to scope:

- TypeScript type checking and project lint;
- unit and component tests;
- routing, state, form, and API-contract tests;
- Playwright or Cypress E2E in target browsers;
- visual regression, responsive, keyboard, and accessibility checks;
- SSR/hydration, SSE/WebSocket, file, authorization, cache, and offline scenarios;
- bundle, Core Web Vitals, and memory baselines.

At minimum, verify normal, loading, empty, error, disabled, repeated click, refresh, route switching, insufficient authorization, timeout/failure, and asynchronous races. A passing build does not prove interaction works; fully mocked tests are not integration validation; static checks are not browser runtime validation.

## 5. Review Output

Cover framework and version, components and state, request races, authorization and security, SSR and real-time connections, resource release, forms/lists/files, performance, accessibility, build and test evidence, version compatibility, and unverified items.

## 6. Design Systems, SEO, and Browser Compatibility

For design systems and component libraries, check design tokens, themes, CSS variables, public component contracts, version compatibility, style isolation, lazy loading, and consumer migration. Visual uniformity must not break accessibility, business semantics, or legacy compatibility.

For public web pages, check as needed: title/meta, canonical, robots, sitemap, Open Graph, structured data, semantic HTML, SSR/SSG crawlability, redirects, and error states. Base SEO conclusions on build artifacts, actual responses, and crawl tests, not only components.

Browser compatibility follows project `browserslist`, enterprise terminals, WebView/device versions, and real statistics. Check polyfills, CSS features, module formats, Intl, file/media APIs, and fallbacks. Passing on the local latest Chromium does not prove every target browser passes.
