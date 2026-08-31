#!/usr/bin/env python3
"""Read-only, bounded frontend stack detector using only Python standard library."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

FRAMEWORKS = {
    "vue": {"vue", "nuxt", "@nuxt/kit"},
    "react": {"react", "react-dom", "next", "@remix-run/react"},
    "preact": {"preact", "@preact/signals", "preact-router"},
    "angular": {"@angular/core", "@angular/cli"},
    "svelte": {"svelte", "@sveltejs/kit"},
    "astro": {"astro"},
    "solid": {"solid-js", "@solidjs/start"},
    "qwik": {"@builder.io/qwik", "@builder.io/qwik-city"},
    "ember": {"ember-source", "ember-cli"},
    "web-components": {"lit", "lit-element", "@lit/reactive-element"},
    "lightweight-web": {"alpinejs", "htmx.org", "@hotwired/stimulus", "@hotwired/turbo"},
    "legacy": {"jquery", "layui"},
}

HYBRID_RUNTIMES = {
    "ionic": {"@ionic/core", "@ionic/react", "@ionic/vue", "@ionic/angular"},
    "capacitor": {"@capacitor/core"},
    "electron-renderer": {"electron"},
    "tauri-renderer": {"@tauri-apps/api"},
}

BUILD_TOOLS = {
    "vite", "webpack", "rspack", "rollup", "parcel", "esbuild", "turbopack",
    "@angular-devkit/build-angular", "@vitejs/plugin-vue", "@vitejs/plugin-react",
}
TEST_TOOLS = {
    "vitest", "jest", "@playwright/test", "cypress", "karma", "jasmine",
    "@testing-library/react", "@testing-library/vue", "@testing-library/angular",
    "@testing-library/svelte", "storybook", "@storybook/test",
}
STATE_DATA_TOOLS = {
    "pinia", "vuex", "redux", "@reduxjs/toolkit", "zustand", "jotai", "recoil",
    "@ngrx/store", "@tanstack/react-query", "@tanstack/vue-query", "swr",
    "@apollo/client", "urql", "rxjs",
}
STYLE_TOOLS = {
    "tailwindcss", "sass", "less", "stylus", "postcss", "styled-components",
    "@emotion/react", "vanilla-extract", "unocss",
}
MICROFRONTEND = {
    "single-spa", "qiankun", "@module-federation/enhanced", "@module-federation/runtime",
}
PWA_TOOLS = {"workbox-window", "workbox-webpack-plugin", "vite-plugin-pwa", "@angular/service-worker"}
NODE_BACKEND = {"express", "fastify", "koa", "@nestjs/core", "hapi", "@hapi/hapi", "adonisjs"}

LOCKFILES = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}

CONFIG_HINTS = {
    "nuxt.config.ts": "vue",
    "nuxt.config.js": "vue",
    "next.config.js": "react",
    "next.config.mjs": "react",
    "next.config.ts": "react",
    "remix.config.js": "react",
    "remix.config.mjs": "react",
    "angular.json": "angular",
    "svelte.config.js": "svelte",
    "svelte.config.ts": "svelte",
    "astro.config.mjs": "astro",
    "astro.config.ts": "astro",
    "ember-cli-build.js": "ember",
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "vite.config.mjs": "vite",
    "webpack.config.js": "webpack",
    "webpack.config.ts": "webpack",
    "rspack.config.js": "rspack",
    "rspack.config.ts": "rspack",
    "ionic.config.json": "hybrid-runtime",
    "capacitor.config.ts": "hybrid-runtime",
    "capacitor.config.js": "hybrid-runtime",
    "src-tauri/tauri.conf.json": "hybrid-runtime",
}

WORKSPACE_HINTS = {
    "pnpm-workspace.yaml": "pnpm-workspace",
    "nx.json": "nx",
    "turbo.json": "turborepo",
    "lerna.json": "lerna",
}

SOURCE_EXTENSIONS = {
    ".vue": "vue",
    ".svelte": "svelte",
    ".astro": "astro",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".html": "html",
    ".htm": "html",
    ".jsp": "jsp",
    ".jspx": "jsp",
}
STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl"}
SKIP_DIRS = {
    ".git", ".svn", ".hg", ".idea", ".vscode", "node_modules", "dist", "build",
    "target", "coverage", ".next", ".nuxt", ".svelte-kit", ".output", "out", "vendor",
    "archive", "__pycache__",
}

RENDER_HINTS = {
    "next": "SSR/SSG/ISR/Hybrid candidate",
    "nuxt": "SSR/SSG/Hybrid candidate",
    "@sveltejs/kit": "SSR/SSG/Hybrid candidate",
    "@remix-run/react": "SSR/Streaming candidate",
    "astro": "SSG/SSR/Islands candidate",
    "@solidjs/start": "SSR/SSG candidate",
    "@builder.io/qwik-city": "SSR/Resumability candidate",
}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # keep parse failure as evidence, never hide it
        return {}, str(exc)


def package_dependencies(package):
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = package.get(key, {})
        if isinstance(value, dict):
            deps.update(value)
    return deps


def bounded_source_scan(root, max_depth, max_files):
    counts = Counter()
    samples = {}
    scanned = 0
    truncated = False

    for current, dirs, files in os.walk(str(root)):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue

        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".cache")]
        if depth >= max_depth:
            dirs[:] = []

        for filename in files:
            scanned += 1
            if scanned > max_files:
                truncated = True
                dirs[:] = []
                break

            suffix = Path(filename).suffix.lower()
            family = SOURCE_EXTENSIONS.get(suffix)
            if family:
                counts[family] += 1
                samples.setdefault(family, [])
                if len(samples[family]) < 5:
                    samples[family].append(str((current_path / filename).relative_to(root)))
            elif suffix in STYLE_EXTENSIONS:
                counts["style"] += 1
                samples.setdefault("style", [])
                if len(samples["style"]) < 3:
                    samples["style"].append(str((current_path / filename).relative_to(root)))
        if truncated:
            break

    return {
        "scanned_files": min(scanned, max_files),
        "truncated": truncated,
        "counts": dict(sorted(counts.items())),
        "samples": samples,
    }


def detect(root, max_depth=6, max_files=2000):
    package_path = root / "package.json"
    package, package_error = read_json(package_path) if package_path.is_file() else ({}, None)
    deps = package_dependencies(package)
    names = set(deps)

    frameworks = []
    evidence = []
    versions = {}
    for family, packages in FRAMEWORKS.items():
        hits = sorted(names & packages)
        if hits:
            frameworks.append(family)
            evidence.append({"type": "package", "family": family, "values": hits})
            for name in hits:
                versions[name] = deps.get(name)

    configs = []
    frontend_config_detected = False
    hybrid_config_detected = False
    for relative_name, hint in CONFIG_HINTS.items():
        if (root / relative_name).exists():
            configs.append(relative_name)
            if hint in FRAMEWORKS and hint not in frameworks:
                frameworks.append(hint)
            if hint == "hybrid-runtime":
                hybrid_config_detected = True
            else:
                frontend_config_detected = True
            evidence.append({"type": "config", "family": hint, "values": [relative_name]})

    source_scan = bounded_source_scan(root, max_depth=max_depth, max_files=max_files)
    source_families = set(source_scan["counts"])
    for family in ("vue", "svelte", "astro"):
        if family in source_families and family not in frameworks:
            frameworks.append(family)
            evidence.append({"type": "source", "family": family, "values": source_scan["samples"].get(family, [])})

    static_or_legacy = bool(source_families & {"html", "jsp"})
    jsx_like = bool(source_families & {"jsx", "tsx"})
    if static_or_legacy and not frameworks:
        frameworks.append("legacy")
        evidence.append({"type": "source", "family": "legacy", "values": source_scan["samples"].get("jsp", []) + source_scan["samples"].get("html", [])})

    hybrid = {}
    for family, packages in HYBRID_RUNTIMES.items():
        hits = sorted(names & packages)
        if hits:
            hybrid[family] = hits
            for name in hits:
                versions[name] = deps.get(name)

    # Ionic packages can identify the UI framework even when package metadata is sparse.
    ionic_framework_map = {
        "@ionic/react": "react",
        "@ionic/vue": "vue",
        "@ionic/angular": "angular",
    }
    for package_name, family in ionic_framework_map.items():
        if package_name in names and family not in frameworks:
            frameworks.append(family)

    locks = [{"file": name, "manager": manager} for name, manager in LOCKFILES.items() if (root / name).exists()]
    package_manager_field = package.get("packageManager") if isinstance(package.get("packageManager"), str) else None
    effective_package_manager = package_manager_field.split("@", 1)[0] if package_manager_field else (locks[0]["manager"] if len(locks) == 1 else None)

    scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
    script_text = " ".join(str(value) for value in scripts.values()).lower()
    build_tools = sorted(names & BUILD_TOOLS)
    for tool in sorted(BUILD_TOOLS):
        token = tool.split("/", 1)[-1]
        if token in script_text and tool not in build_tools:
            build_tools.append(tool)

    test_tools = sorted(names & TEST_TOOLS)
    state_data_tools = sorted(names & STATE_DATA_TOOLS)
    style_tools = sorted(names & STYLE_TOOLS)
    microfrontend_packages = sorted(names & MICROFRONTEND)
    pwa_tools = sorted(names & PWA_TOOLS)
    node_backend_packages = sorted(names & NODE_BACKEND)

    workspace_values = []
    workspaces_field = package.get("workspaces")
    if isinstance(workspaces_field, list):
        workspace_values.extend(str(item) for item in workspaces_field)
    elif isinstance(workspaces_field, dict):
        packages = workspaces_field.get("packages")
        if isinstance(packages, list):
            workspace_values.extend(str(item) for item in packages)
    workspace_files = [{"file": name, "type": kind} for name, kind in WORKSPACE_HINTS.items() if (root / name).exists()]

    rendering_hints = sorted({label for package_name, label in RENDER_HINTS.items() if package_name in names})
    if "html" in source_families and not rendering_hints:
        rendering_hints.append("CSR/MPA/static candidate")
    if "jsp" in source_families:
        rendering_hints.append("server-rendered MPA candidate")

    frontend_source_detected = bool(source_families & {"vue", "svelte", "astro", "jsx", "tsx", "html", "jsp"})
    frontend_detected = bool(frameworks or frontend_config_detected or frontend_source_detected)
    hybrid_detected = bool(hybrid) and (frontend_detected or hybrid_config_detected)

    if frontend_detected and node_backend_packages:
        classification = "fullstack-web"
    elif hybrid_detected:
        classification = "hybrid-web"
    elif frontend_detected:
        classification = "frontend"
    elif node_backend_packages:
        classification = "node-backend"
    else:
        classification = "unknown"

    if package_path.is_file() and (frameworks or frontend_config_detected):
        confidence = "high"
    elif frontend_source_detected or node_backend_packages or hybrid_detected:
        confidence = "medium"
    else:
        confidence = "low"

    warnings = []
    if len(locks) > 1:
        warnings.append("检测到多个锁文件，需确认唯一有效包管理器")
    modern = [family for family in frameworks if family not in {"legacy", "lightweight-web"}]
    if len(modern) > 1:
        warnings.append("检测到多个现代框架，可能是 Monorepo、微前端、迁移期或混合项目；应先划分目录边界")
    if package_error:
        warnings.append("package.json 解析失败: " + package_error)
    if classification == "node-backend":
        warnings.append("仅检测到 Node.js 服务端依赖，不应仅因存在 package.json 激活前端技能")
    if classification == "fullstack-web":
        warnings.append("同时检测到浏览器与 Node.js 服务端能力；前端和服务端逻辑必须分边界加载规则")
    if hybrid:
        warnings.append("检测到 WebView/桌面混合运行时；Renderer/Web UI 可使用前端规则，主进程、原生桥或系统能力必须单独审查")
    if hybrid and not hybrid_detected:
        warnings.append("仅检测到混合运行时依赖，尚不足以证明存在浏览器渲染层")
    if microfrontend_packages:
        warnings.append("检测到微前端依赖，应读取 microfrontend-monorepo-rules.md")
    if workspace_values or workspace_files:
        warnings.append("检测到 Workspace/Monorepo；根目录结论不能自动覆盖所有子项目")
    if jsx_like and not any(family in frameworks for family in {"react", "preact", "solid", "qwik"}):
        warnings.append("检测到 JSX/TSX 源码但未确认具体框架，需结合构建插件和入口文件确认")
    if source_scan["truncated"]:
        warnings.append("源码扫描达到上限，结果是有界候选快照，不代表完整仓库清单")
    if static_or_legacy and not package_path.is_file():
        warnings.append("未发现 package.json，已根据 HTML/JSP 等源码签名识别传统或静态前端")

    return {
        "project_dir": str(root.resolve()),
        "classification": classification,
        "confidence": confidence,
        "frameworks": frameworks,
        "detected_versions": versions,
        "hybrid_runtimes": hybrid,
        "package_manager_field": package_manager_field,
        "effective_package_manager": effective_package_manager,
        "lockfiles": locks,
        "workspace_patterns": workspace_values,
        "workspace_files": workspace_files,
        "build_tools": build_tools,
        "test_tools": test_tools,
        "state_data_tools": state_data_tools,
        "style_tools": style_tools,
        "pwa_tools": pwa_tools,
        "microfrontend_packages": microfrontend_packages,
        "node_backend_packages": node_backend_packages,
        "node_engine": (package.get("engines") or {}).get("node") if isinstance(package.get("engines"), dict) else None,
        "config_files": configs,
        "rendering_hints": rendering_hints,
        "source_scan": source_scan,
        "evidence": evidence,
        "warnings": warnings,
        "recommended_references": recommend_references(frameworks, classification, bool(microfrontend_packages), bool(hybrid)),
    }


def recommend_references(frameworks, classification, microfrontend, hybrid):
    frontend_classes = {"frontend", "fullstack-web", "hybrid-web"}
    if classification not in frontend_classes:
        return []

    refs = ["frontend-core-rules.md"]
    mapping = {
        "vue": "vue-nuxt-rules.md",
        "react": "react-next-remix-rules.md",
        "preact": "other-modern-frameworks-rules.md",
        "angular": "angular-rules.md",
        "svelte": "svelte-sveltekit-rules.md",
        "astro": "other-modern-frameworks-rules.md",
        "solid": "other-modern-frameworks-rules.md",
        "qwik": "other-modern-frameworks-rules.md",
        "ember": "other-modern-frameworks-rules.md",
        "web-components": "other-modern-frameworks-rules.md",
        "lightweight-web": "other-modern-frameworks-rules.md",
        "legacy": "legacy-frontend-rules.md",
    }
    for family in frameworks:
        ref = mapping.get(family)
        if ref and ref not in refs:
            refs.append(ref)
    if hybrid and "frontend-security-runtime-rules.md" not in refs:
        refs.append("frontend-security-runtime-rules.md")
    if microfrontend and "microfrontend-monorepo-rules.md" not in refs:
        refs.append("microfrontend-monorepo-rules.md")
    return refs


def markdown(data):
    versions = ", ".join("{}={}".format(k, v) for k, v in sorted(data["detected_versions"].items())) or "未识别"
    source_counts = ", ".join("{}={}".format(k, v) for k, v in data["source_scan"]["counts"].items()) or "未识别"
    lines = [
        "# 前端技术栈检测结果",
        "",
        "- 目录：{}".format(data["project_dir"]),
        "- 分类：{}".format(data["classification"]),
        "- 置信度：{}".format(data["confidence"]),
        "- 框架：{}".format(", ".join(data["frameworks"]) or "未识别"),
        "- 版本证据：{}".format(versions),
        "- 包管理器：{}".format(data["effective_package_manager"] or "未识别"),
        "- 锁文件：{}".format(", ".join(item["file"] for item in data["lockfiles"]) or "未识别"),
        "- 构建工具：{}".format(", ".join(data["build_tools"]) or "未识别"),
        "- 测试工具：{}".format(", ".join(data["test_tools"]) or "未识别"),
        "- 渲染候选：{}".format(", ".join(data["rendering_hints"]) or "未识别"),
        "- 源码签名：{}".format(source_counts),
        "- 推荐规则：{}".format(", ".join(data["recommended_references"]) or "无"),
    ]
    if data["warnings"]:
        lines += ["", "## 警告"] + ["- " + warning for warning in data["warnings"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="只读、有界的前端技术栈候选检测器")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--max-depth", type=int, default=6, help="源码签名扫描最大目录深度，默认 6")
    parser.add_argument("--max-files", type=int, default=2000, help="源码签名扫描最大文件数，默认 2000")
    args = parser.parse_args()

    root = Path(args.project_dir)
    if not root.is_dir():
        print("项目目录不存在: " + str(root), file=sys.stderr)
        return 2
    if args.max_depth < 0 or args.max_files <= 0:
        print("max-depth 必须大于等于 0，max-files 必须大于 0", file=sys.stderr)
        return 2

    data = detect(root, max_depth=args.max_depth, max_files=args.max_files)
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
