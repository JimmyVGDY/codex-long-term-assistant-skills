from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ux-benchmark.py"
SPEC = importlib.util.spec_from_file_location("ux_benchmark_contract", SCRIPT)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class UxBenchmarkTests(unittest.TestCase):
    def test_collect_compare_and_reject_mixed_fixture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ux-benchmark-") as temp:
            root = Path(temp)
            before = root / "before.json"
            after = root / "after.json"
            compared = root / "compare.json"
            command = json.dumps([sys.executable, "-c", "print('fixture')"])
            common = [sys.executable, str(SCRIPT), "collect", "--scenario-id", "simple-local-fix",
                      "--package-version", "7.10.0", "--source-sha", "a" * 40, "--fixture",
                      str(ROOT / "tests" / "fixtures" / "ux-benchmark"), "--sample-count", "2",
                      "--command-json", command]
            subprocess.run([*common, "--output", str(before)], cwd=ROOT, check=True)
            subprocess.run([*common, "--output", str(after)], cwd=ROOT, check=True)
            subprocess.run([sys.executable, str(SCRIPT), "compare", "--before", str(before),
                            "--after", str(after), "--output", str(compared)], cwd=ROOT, check=True)
            report = json.loads(compared.read_text(encoding="utf-8"))
            self.assertEqual("ux-benchmark-compare/1", report["schema"])
            self.assertIn("median_delta_ms", report)
            value = json.loads(before.read_text(encoding="utf-8"))
            value["summary"]["median_duration_ms"] = -99999
            before.write_text(json.dumps(value), encoding="utf-8")
            recalculated = root / "recomputed.json"
            subprocess.run([sys.executable, str(SCRIPT), "compare", "--before", str(before),
                            "--after", str(after), "--output", str(recalculated)], cwd=ROOT, check=True)
            self.assertGreaterEqual(json.loads(recalculated.read_text(encoding="utf-8"))["before"]["median_duration_ms"], 0)
            value = json.loads(after.read_text(encoding="utf-8"))
            value["samples"][0]["fixture_digest"] = "b" * 64
            after.write_text(json.dumps(value), encoding="utf-8")
            failed = subprocess.run([sys.executable, str(SCRIPT), "compare", "--before", str(before),
                                     "--after", str(after), "--output", str(root / "mixed.json")],
                                    cwd=ROOT, capture_output=True)
            self.assertNotEqual(0, failed.returncode)
            self.assertFalse((root / "mixed.json").exists())

    def test_percentile_requires_twenty_timings_and_uses_actual_sample_count(self):
        samples = [{"outcome": "PASS", "duration_ms": value} for value in range(1, 101)]
        self.assertIsNone(BENCHMARK._summary(samples[:3])["p95_duration_ms"])
        self.assertEqual(19, BENCHMARK._summary(samples[:20])["p95_duration_ms"])
        self.assertEqual(95, BENCHMARK._summary(samples)["p95_duration_ms"])

    def test_unknown_duration_does_not_reclassify_a_success_as_failure(self):
        summary = BENCHMARK._summary([{"outcome": "PASS", "duration_ms": "UNKNOWN"}])
        self.assertEqual((1, 0, 0), (summary["success_count"], summary["failure_count"], summary["timing_sample_count"]))

    def test_nested_metadata_and_nonfinite_durations_are_rejected(self):
        for item in ({"outcome": "PASS", "limitations": [{"private": "payload"}]},
                     {"outcome": "PASS", "duration_ms": float("nan")},
                     {"outcome": "PASS", "duration_ms": -1}):
            with self.subTest(item=item), self.assertRaises(SystemExit):
                BENCHMARK._observation(item)

    def test_benchmark_output_cannot_overwrite_an_existing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input.json"
            target.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                BENCHMARK._write(target, {"samples": []})
            self.assertEqual("original", target.read_text(encoding="utf-8"))

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

    def test_explicit_missing_fixture_never_launches_command_or_creates_output(self):
        with tempfile.TemporaryDirectory(prefix="ux-missing-") as temp:
            root = Path(temp)
            marker, output = root / "executed", root / "out.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "collect", "--scenario-id", "missing",
                 "--package-version", "7.10.0", "--source-sha", "a" * 40,
                 "--fixture", str(root / "missing"), "--sample-count", "1",
                 "--command-json", json.dumps([sys.executable, "-c",
                    "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('ran')"]),
                 "--output", str(output)], cwd=ROOT, capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(marker.exists())
            self.assertFalse(output.exists())
