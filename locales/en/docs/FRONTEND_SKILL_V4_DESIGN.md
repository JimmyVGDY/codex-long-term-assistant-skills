# v4.0 General Frontend Engineering Skill Design

## Goal

Rename and expand `vue-frontend-engineering` directly into cross-framework `frontend-engineering`, while controlling automatic triggers, context use, framework-semantic contamination, and confusion among browser, server, and native runtime boundaries.

## Main Improvements

1. Rename directly without a compatibility alias, preventing duplicate discovery, cache fragmentation, and competing Skills.
2. Separate general core rules from framework-specific rules and load on demand.
3. Cover Vue/Nuxt, React/Next/Remix, Preact, Angular, Svelte/SvelteKit, Astro/Solid/Qwik/Ember/Web Components, Alpine/HTMX, Ionic/Capacitor, and legacy pages.
4. Define Browser, SSR/Edge, WebView, PWA, extension, Electron/Tauri renderer, main-process, and native-bridge boundaries.
5. Manage security/runtime, quality/performance, design-system/SEO, and microfrontend/monorepo topics separately.
6. Add a read-only bounded stack detector for packages, configuration, workspaces, source signatures, static HTML/JSP, hybrid runtimes, and pure Node.js-backend exclusion.
7. Require server logic in full-stack frontend frameworks to meet backend standards.
8. Add negative routing cases for Node.js servers and Electron/Tauri main processes to prevent false triggers from `package.json` or desktop dependencies.
9. Add stack snapshot, review report, and validation matrix templates.
10. Reject `__pycache__` and `.pyc` in package validation so local runtime artifacts cannot enter distribution.

## Progressive Loading

`SKILL.md` retains triggers, boundaries, and loading decisions. General core rules are mandatory; framework, security, quality, and microfrontend references load per task. Each independent application normally loads one primary framework reference. A multi-application repository is partitioned by directory first.

## Stack-Detector Boundary

The detector:

- is read-only and does not install dependencies or run project scripts;
- scans at most six levels and 2,000 files by default, excluding dependencies, build output, and version-control directories;
- reports classification, confidence, frameworks/versions, workspace, build/test tools, rendering candidates, source signatures, and warnings;
- recognizes legacy JSP/HTML and browser-plus-Node full-stack candidates;
- produces candidate evidence only and does not replace actual entries, configuration, source, or runtime validation.

## Breaking Change

Explicit invocation changes from `vue-frontend-engineering` to `frontend-engineering`. Installation backs up and removes the old directory; validation treats any old-directory residue as a failure.
