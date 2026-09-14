from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ux-benchmark.py"


class UxBenchmarkTests(unittest.TestCase):
    def test_collect_compare_and_reject_mixed_fixture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ux-benchmark-") as temp:
            root = Path(temp)
            before = root / "before.json"
            after = root / "after.json"
            compared = root / "compare.json"
            command = json.dumps([sys.executable, "-c", "print('fixture')"])
            common = [sys.executable, str(SCRIPT), "collect", "--scenario-id", "simple-local-fix",
                      "--package-version", "7.10.0", "--source-sha", "sha", "--fixture",
                      str(ROOT / "tests" / "fixtures" / "ux-benchmark"), "--sample-count", "2",
                      "--command-json", command]
            subprocess.run([*common, "--output", str(before)], cwd=ROOT, check=True)
            subprocess.run([*common, "--output", str(after)], cwd=ROOT, check=True)
            subprocess.run([sys.executable, str(SCRIPT), "compare", "--before", str(before),
                            "--after", str(after), "--output", str(compared)], cwd=ROOT, check=True)
            report = json.loads(compared.read_text(encoding="utf-8"))
            self.assertEqual("ux-benchmark-compare/1", report["schema"])
            self.assertIn("median_delta_ms", report)

    def test_import_observations_enforces_whitelist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ux-observation-") as temp:
            root = Path(temp)
            source = root / "source.json"
            output = root / "output.json"
            source.write_text(json.dumps({"samples": [{"schema": "ux-benchmark/1", "scenario_id": "x",
                                                          "fixture_digest": "d", "outcome": "PASS"}]}), encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPT), "import-observations", "--input", str(source),
                            "--output", str(output)], cwd=ROOT, check=True)
            self.assertEqual("ux-benchmark/1", json.loads(output.read_text(encoding="utf-8"))["schema"])

    def test_collect_rejects_nonpositive_sample_count(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ux-invalid-") as temp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "collect", "--scenario-id", "x",
                 "--package-version", "7.10.0", "--source-sha", "sha",
                 "--sample-count", "0", "--command-json", json.dumps([sys.executable, "-c", "pass"]),
                 "--output", str(Path(temp) / "out.json")],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertNotEqual(0, result.returncode)
