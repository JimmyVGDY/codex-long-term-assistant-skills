"""中文：直接运行收集器时不依赖测试发现顺序来解析跨测试导入。

English: Direct collector invocation resolves cross-test imports without relying on discovery order.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CollectorImportBoundaryTests(unittest.TestCase):
    def test_direct_cli_collects_package_fixture_imports_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)
            environment["CODEX_HOME"] = str(Path(directory) / "codex-home")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/validation_evidence.py"), "collect",
                 "--start-dir", str(ROOT / "tests"), "--pattern", "test_g6_retry_v1.py",
                 "--suite", "import-boundary", "--output", str(output)],
                cwd=directory, env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreaterEqual(report["executed_test_count"], 3)
            self.assertEqual(set(report["outcome_counts"]), {"PASS"})
            self.assertFalse(any("_FailedTest" in row["id"] for row in report["test_cases"]))


if __name__ == "__main__":
    unittest.main()
