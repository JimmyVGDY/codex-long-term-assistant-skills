# Vanilla JavaScript, jQuery, Layui, JSP, and Legacy Frontend Rules

> Load for projects without a modern framework, server templates, jQuery/Layui, JSP, legacy multipage applications, or historical plugins, together with `frontend-core-rules.md`. Old code does not authorize an autonomous rewrite to a modern framework.

## 1. Project and Load Order

Confirm:

- vanilla scripts, jQuery, Layui, JSP/template engine, and plugin versions;
- `<script>` load order, globals, AMD/CMD, or legacy module patterns;
- browser targets, polyfills, and static-asset caching;
- server-rendered pages versus Ajax updates;
- backend response shape, character encoding, and download responses.

Legacy dependencies may be referenced indirectly through globals, reflection-like calls, or page order. Static search alone is not enough to delete them.

## 2. DOM, Events, and Global State

Check:

- duplicate binding, delegation, unbinding, and dynamic DOM;
- stale handlers, timers, and plugin instances after partial refresh;
- globals, naming collisions, and cross-page state pollution;
- DOM queries, looped mutations, layout thrashing, and large-list performance;
- plugin initialization, destruction, duplicate instances, and compatibility;
- inline events, string execution, and dynamic scripts.

Prefer stable event delegation for dynamic lists, while preventing duplicate registration and unremovable handlers.

## 3. Ajax, Callbacks, and Races

Check:

- callback nesting, error branches, timeouts, cancellation, and duplicate submission;
- callbacks mutating destroyed DOM after navigation or dialog closure;
- out-of-order responses and stale-result overwrite;
- global Ajax interceptors and expired-token handling;
- form serialization, encoding, dates, money, and null values;
- contract compatibility of server HTML fragments and JSON fields.

Do not block the browser main thread with synchronous Ajax.

## 4. Layui, JSP, and Server Templates

Check:

- Layui module loading, table reloads, form rendering, layer closure, and duplicate event binding;
- correct escaping of HTML, JavaScript strings, and URLs emitted by JSP/templates;
- XSS, quote, and encoding issues from server variables interpolated into scripts;
- compatibility among pages, Servlet/Controller, download streams, and response headers;
- old page caches, static-asset versions, and browser fallbacks.

Hidden frontend buttons do not replace authorization in Struts, Spring, Servlet, or another backend.

## 5. Security and Incremental Modernization

- Do not put untrusted content directly into `innerHTML`, `document.write`, or string templates.
- Do not use `eval`, string `setTimeout`, or uncontrolled dynamic scripts.
- Validate URLs, redirects, download file names, and rich text.
- Modernize incrementally by isolating modules and adding tests and compatibility layers; do not migrate the whole framework within a small repair.
- Preserve real constraints from old browsers, plugins, and server templates.

## 6. Legacy Frontend Review

- Duplicate event binding, unbinding, globals, and plugin lifecycle.
- Ajax callbacks, races, synchronous blocking, and error recovery.
- JSP/template escaping, XSS, encoding, and backend contracts.
- Layui table, form, and layer state.
- Static caching, load order, legacy browsers, and incremental compatibility.
- Unnecessary framework rewrites introduced for a local issue.
