#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_frontend_stack.py"
SPEC = importlib.util.spec_from_file_location("frontend_detector", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DetectorTests(unittest.TestCase):
    def fixture(self, dependencies=None, files=(), package_extra=None, raw_package=None):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        if raw_package is not None:
            (root / "package.json").write_text(raw_package, encoding="utf-8")
        elif dependencies is not None or package_extra is not None:
            package = {"dependencies": dependencies or {}}
            package.update(package_extra or {})
            (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
        for relative_path in files:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return root

    def test_vue(self):
        root = self.fixture({"vue": "3", "pinia": "2"}, ("pnpm-lock.yaml", "src/App.vue"))
        data = MODULE.detect(root)
        self.assertIn("vue", data["frameworks"])
        self.assertEqual("frontend", data["classification"])
        self.assertIn("vue-nuxt-rules.md", data["recommended_references"])

    def test_next_with_node_backend_is_fullstack(self):
        root = self.fixture({"react": "19", "next": "15", "express": "5"}, ("package-lock.json", "app/page.tsx"))
        data = MODULE.detect(root)
        self.assertEqual("fullstack-web", data["classification"])
        self.assertTrue(any("浏览器与 Node.js 服务端" in warning for warning in data["warnings"]))

    def test_angular(self):
        root = self.fixture({"@angular/core": "20"}, ("angular.json",))
        self.assertIn("angular", MODULE.detect(root)["frameworks"])

    def test_node_backend_excluded(self):
        root = self.fixture({"express": "5"}, ("package-lock.json", "src/server.js"))
        data = MODULE.detect(root)
        self.assertEqual("node-backend", data["classification"])
        self.assertEqual([], data["recommended_references"])

    def test_multiple_locks_warn(self):
        root = self.fixture({"svelte": "5"}, ("package-lock.json", "pnpm-lock.yaml", "src/App.svelte"))
        self.assertTrue(any("多个锁文件" in warning for warning in MODULE.detect(root)["warnings"]))

    def test_plain_jsp_without_package(self):
        root = self.fixture(files=("src/main/webapp/WEB-INF/views/index.jsp", "src/main/webapp/css/app.css"))
        data = MODULE.detect(root)
        self.assertEqual("frontend", data["classification"])
        self.assertIn("legacy", data["frameworks"])
        self.assertIn("legacy-frontend-rules.md", data["recommended_references"])

    def test_static_html_without_package(self):
        root = self.fixture(files=("public/index.html", "public/app.js", "public/app.css"))
        data = MODULE.detect(root)
        self.assertEqual("frontend", data["classification"])
        self.assertEqual("medium", data["confidence"])

    def test_preact_uses_other_modern_rules(self):
        root = self.fixture({"preact": "10", "@preact/signals": "1"}, ("vite.config.ts", "src/app.tsx"))
        data = MODULE.detect(root)
        self.assertIn("preact", data["frameworks"])
        self.assertIn("other-modern-frameworks-rules.md", data["recommended_references"])

    def test_ionic_react_is_hybrid_web(self):
        root = self.fixture({"@ionic/react": "8", "@capacitor/core": "7", "react": "19"}, ("ionic.config.json", "src/App.tsx"))
        data = MODULE.detect(root)
        self.assertEqual("hybrid-web", data["classification"])
        self.assertIn("react", data["frameworks"])
        self.assertIn("frontend-security-runtime-rules.md", data["recommended_references"])

    def test_workspace_warning(self):
        root = self.fixture({"react": "19"}, ("pnpm-workspace.yaml", "apps/web/src/App.tsx"), {"workspaces": ["apps/*"]})
        data = MODULE.detect(root)
        self.assertTrue(data["workspace_patterns"])
        self.assertTrue(any("Workspace/Monorepo" in warning for warning in data["warnings"]))

    def test_malformed_package_is_reported(self):
        root = self.fixture(files=("index.html",), raw_package="{bad json")
        data = MODULE.detect(root)
        self.assertEqual("frontend", data["classification"])
        self.assertTrue(any("package.json 解析失败" in warning for warning in data["warnings"]))

    def test_electron_dependency_alone_does_not_prove_frontend(self):
        root = self.fixture({"electron": "35"}, ("main.js",))
        data = MODULE.detect(root)
        self.assertEqual("unknown", data["classification"])
        self.assertTrue(any("尚不足以证明" in warning for warning in data["warnings"]))


if __name__ == "__main__":
    unittest.main()
