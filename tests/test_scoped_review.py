from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "scoped_review.py"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


class ScopedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scoped-review-")
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "target.py").write_text("from dep import value\nRESULT = value\n", encoding="utf-8")
        (self.repo / "dep.py").write_text("value = 1\n", encoding="utf-8")
        (self.repo / "config.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "authority.lock").write_text("v1\n", encoding="utf-8")
        (self.repo / "other.md").write_text("one\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "fixture")
        self.manifest = self.base / "scope.json"

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout.strip().startswith("{") else result.stderr

    def create(self, *extra, expected=0):
        return self.invoke("create", "--repo-path", str(self.repo), "--output", str(self.manifest),
                           "--target", "target.py", "--config", "config.json",
                           "--authority", "authority.lock", *extra, expected=expected)

    def test_discovers_python_dependency_and_validates_integrity(self):
        result = self.create()
        entries = {item["path"]: item["category"] for item in result["entries"]}
        self.assertEqual("target", entries["target.py"])
        self.assertEqual("discovered-dependency", entries["dep.py"])
        self.assertTrue(result["closure_complete"])
        validated = self.invoke("validate", "--manifest", str(self.manifest))
        self.assertEqual("VALID", validated["status"])

    def test_unrelated_change_warns_but_dependency_change_is_stale(self):
        self.create()
        (self.repo / "other.md").write_text("two\n", encoding="utf-8")
        fresh = self.invoke("freshness", "--repo-path", str(self.repo), "--manifest", str(self.manifest))
        self.assertEqual("FRESH", fresh["status"])
        self.assertEqual(["other.md"], fresh["warnings"])
        (self.repo / "dep.py").write_text("value = 2\n", encoding="utf-8")
        stale = self.invoke("freshness", "--repo-path", str(self.repo), "--manifest", str(self.manifest), expected=2)
        self.assertEqual("STALE", stale["status"])
        self.assertIn("dep.py:changed", stale["stale"])

    def test_dynamic_import_is_incomplete_not_fresh(self):
        (self.repo / "target.py").write_text("import importlib\nRESULT = importlib.import_module('dep')\n", encoding="utf-8")
        result = self.create()
        self.assertFalse(result["closure_complete"])
        incomplete = self.invoke("freshness", "--repo-path", str(self.repo), "--manifest", str(self.manifest), expected=3)
        self.assertEqual("INCOMPLETE", incomplete["status"])
        self.assertTrue(incomplete["unknown_dependencies"])

    def test_missing_and_outside_paths_fail_closed(self):
        missing = self.invoke("create", "--repo-path", str(self.repo), "--output", str(self.manifest),
                              "--target", "missing.py", expected=1)
        self.assertIn("SCOPE_PATH_MISSING", missing)
        outside = self.invoke("create", "--repo-path", str(self.repo), "--output", str(self.manifest),
                              "--target", "../outside.py", expected=1)
        self.assertIn("SCOPE_PATH_INVALID", outside)


if __name__ == "__main__":
    unittest.main()
