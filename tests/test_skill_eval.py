"""中文：产物比较的完整性、边界和错误结果回归。
English: Integrity, boundary, and wrong-result regressions for artifact comparison.
"""
import hashlib
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_eval", ROOT / "scripts/skill-eval.py")
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)


def config(variant="baseline"):
    return {
        "schema": "skill-eval-input/1", "study_id": "study", "case_id": "report",
        "sample_id": "one", "variant": variant, "fixture_digest": "a" * 64,
        "rule_digest": EVAL.digest(EVAL.canonical({})), "rule_files": {}, "source_sha": "d" * 40,
        "environment": {"platform": "windows", "runtime": "python-3.11",
                        "requested_model": "fixed-request", "requested_effort": "medium",
                        "permissions_digest": "e" * 64, "cache_condition": "cold"},
        "initial_files": {}, "allowed_changes": ["result.txt"], "artifacts": ["result.txt"],
        "checks": [{"id": "correct", "kind": "contains", "path": "result.txt", "expected": "42"}],
        "metrics": {"duration_ms": 10, "tool_count": 3},
    }


class ArtifactEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = self.root / "before"
        self.after = self.root / "after"
        self.before.mkdir()
        self.after.mkdir()

    def run_record(self, root, variant, text="answer: 42"):
        (root / "result.txt").write_text(text, encoding="utf-8")
        return EVAL.capture(config(variant), root)

    def test_real_wrong_output_then_correct_candidate(self):
        before = self.run_record(self.before, "baseline", "answer: 0")
        after = self.run_record(self.after, "candidate")
        comparison = EVAL.compare(before, after)
        self.assertEqual("FAILED", before["outcome"])
        self.assertEqual("PASS", after["outcome"])
        self.assertEqual("UNKNOWN", comparison["benefit"])
        self.assertEqual("UNKNOWN", after["semantic_quality"])
        self.assertIsNone(comparison["median_delta_ms"])

    def test_manual_checks_and_unknown_timing_are_not_successes(self):
        value = config()
        value["checks"][0].update(kind="manual", expected="Verify usability independently")
        value["metrics"]["duration_ms"] = "UNKNOWN"
        (self.before / "result.txt").write_text("42", encoding="utf-8")
        record = EVAL.capture(value, self.before)
        self.assertEqual("UNKNOWN", record["outcome"])

    def test_missing_empty_and_incorrect_json_fail(self):
        value = config()
        self.assertEqual("FAILED", EVAL.capture(value, self.before)["outcome"])
        path = self.before / "result.txt"
        path.write_text(" ", encoding="utf-8")
        value["checks"][0].update(kind="nonempty", expected=None)
        self.assertEqual("FAILED", EVAL.capture(value, self.before)["outcome"])
        path.write_text('{"amount":0}', encoding="utf-8")
        value["checks"][0].update(kind="json_equal", expected={"amount": 42})
        self.assertEqual("FAILED", EVAL.capture(value, self.before)["outcome"])
        path.write_text('{"amount":42}', encoding="utf-8")
        self.assertEqual("PASS", EVAL.capture(value, self.before)["outcome"])

    def test_changed_protected_inputs_and_new_unapproved_files_fail(self):
        value = config()
        value["initial_files"]["old.test"] = hashlib.sha256(b"original").hexdigest()
        (self.before / "old.test").write_text("modified", encoding="utf-8")
        (self.before / "result.txt").write_text("42", encoding="utf-8")
        record = EVAL.capture(value, self.before)
        self.assertEqual(["old.test"], record["forbidden_changes"])
        self.assertEqual("FAILED", record["outcome"])

    def test_modified_artifacts_cannot_reuse_old_record(self):
        record = self.run_record(self.before, "baseline")
        (self.before / "result.txt").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(EVAL.EvalError, "STALE_OR_FORGED"):
            EVAL.verify_record(record)

    def test_forged_outcome_is_recomputed_even_with_new_digest(self):
        record = self.run_record(self.before, "baseline", "wrong")
        record["outcome"] = "PASS"
        unsigned = dict(record)
        unsigned.pop("record_digest")
        record["record_digest"] = EVAL.digest(EVAL.canonical(unsigned))
        with self.assertRaisesRegex(EVAL.EvalError, "STALE_OR_FORGED"):
            EVAL.verify_record(record)

    def test_comparisons_reject_changed_environment_fixture_or_checks(self):
        before = self.run_record(self.before, "baseline")
        self.run_record(self.after, "candidate")
        for field in ("fixture_digest", "checks", "environment", "sample_id"):
            value = config("candidate")
            if field == "checks":
                value[field][0]["expected"] = "answer"
            elif field == "environment":
                value[field]["requested_effort"] = "high"
            elif field == "sample_id":
                value[field] = "other"
            else:
                value[field] = "f" * 64
            after = EVAL.capture(value, self.after)
            with self.subTest(field=field), self.assertRaisesRegex(EVAL.EvalError, "INCOMPARABLE"):
                EVAL.compare(before, after)

    def test_independent_directories_are_required(self):
        before = self.run_record(self.before, "baseline")
        after = EVAL.capture(config("candidate"), self.before)
        with self.assertRaisesRegex(EVAL.EvalError, "INDEPENDENT_DIRECTORIES"):
            EVAL.compare(before, after)

    def test_artifact_html_and_metadata_are_escaped_not_executed(self):
        payload = '<script>alert(1)</script><img src="https://invalid.example/x">42'
        before = self.run_record(self.before, "baseline", payload)
        after = self.run_record(self.after, "candidate", payload)
        page = EVAL.render(EVAL.compare(before, after))
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn('<img src="https:', page)
        self.assertIn("default-src 'none'", page)
        self.assertIn("independent quality remain unverified", page)

    def test_bounded_png_preview_never_executes_artifact_markup(self):
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XzGkAAAAASUVORK5CYII=")
        self.assertEqual(EVAL.png_dimensions(png), (1, 1))
        records = []
        for root, variant in ((self.before, "baseline"), (self.after, "candidate")):
            value = config(variant)
            value.update(allowed_changes=["image.png"], artifacts=["image.png"],
                         checks=[{"id": "image", "kind": "nonempty", "path": "image.png", "expected": None}])
            (root / "image.png").write_bytes(png)
            records.append(EVAL.capture(value, root))
        comparison = EVAL.compare(*records)
        page = EVAL.render(comparison)
        self.assertEqual(page.count('src="data:image/png;base64,'), 2)
        self.assertIn("img-src data:", page)
        with patch.object(EVAL, "MAX_PREVIEW_PIXELS", 0):
            limited = EVAL.render(comparison)
        self.assertNotIn("<img", limited)
        self.assertIn("PNG preview omitted", limited)
        self.assertIsNone(EVAL.png_dimensions(png + b"trailing"))

    def test_path_escape_sensitive_files_and_duplicate_paths_rejected(self):
        for name in ("../outside", "/absolute", "folder\\file", ".env", ".ssh/key"):
            value = config()
            value["artifacts"] = [name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                EVAL.validate_input(value)
        value = config()
        value["allowed_changes"].append("result.txt")
        with self.assertRaisesRegex(EVAL.EvalError, "DUPLICATE_PATH"):
            EVAL.validate_input(value)

    def test_duplicate_json_and_nonfinite_metrics_rejected(self):
        source = self.root / "source.json"
        source.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaisesRegex(EVAL.EvalError, "DUPLICATE_JSON"):
            EVAL.read_json(source)
        for number in (-1, float("nan"), float("inf"), True):
            value = config()
            value["metrics"]["duration_ms"] = number
            with self.subTest(number=number), self.assertRaises(EVAL.EvalError):
                EVAL.validate_input(value)

    def test_file_and_total_limits_are_enforced(self):
        (self.before / "result.txt").write_text("42" * 10, encoding="utf-8")
        with patch.object(EVAL, "MAX_FILE_BYTES", 4), self.assertRaises(EVAL.CapabilityError):
            EVAL.snapshot(self.before)
        with patch.object(EVAL, "MAX_TOTAL_BYTES", 4), self.assertRaises(EVAL.CapabilityError):
            EVAL.snapshot(self.before)
        with patch.object(EVAL, "MAX_FILES", 0), self.assertRaises(ValueError):
            EVAL.snapshot(self.before)

    def test_hardlinks_are_rejected(self):
        source = self.root / "outside"
        source.write_text("42", encoding="utf-8")
        (self.before / "result.txt").hardlink_to(source)
        with self.assertRaisesRegex(EVAL.EvalError, "HARDLINK"):
            EVAL.snapshot(self.before)

    def test_cli_returns_structured_failure_for_shared_read_limits(self):
        source = self.root / "input.json"
        source.write_text(json.dumps(config()), encoding="utf-8")
        (self.before / "result.txt").write_bytes(b"x" * (EVAL.MAX_FILE_BYTES + 1))
        output = self.root / "result.json"
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/skill-eval.py"), "capture",
             "--input", str(source), "--artifacts", str(self.before), "--output", str(output)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual("FAILED", json.loads(result.stderr)["status"])
        self.assertFalse(output.exists())

    def test_overwrite_is_refused_and_failure_record_preserved(self):
        before = self.run_record(self.before, "baseline", "wrong")
        output = self.root / "failure.json"
        EVAL.write_new(output, EVAL.canonical(before))
        with self.assertRaises(FileExistsError):
            EVAL.write_new(output, b"replacement")
        self.assertEqual(before, json.loads(output.read_text(encoding="utf-8")))

    def test_source_repository_cannot_be_output_root(self):
        with self.assertRaisesRegex(EVAL.EvalError, "OUTPUT_INSIDE_REPOSITORY"):
            EVAL.external(ROOT / "new-evaluation.json")

    def test_timing_reuses_existing_summary_without_modifying_legacy_contract(self):
        before = self.run_record(self.before, "baseline")
        self.run_record(self.after, "candidate")
        value = config("candidate")
        value["metrics"]["duration_ms"] = 25
        after = EVAL.capture(value, self.after)
        comparison = EVAL.compare(before, after)
        self.assertEqual(15, comparison["median_delta_ms"])
        self.assertIsNone(comparison["metrics"]["baseline"]["p95_duration_ms"])


if __name__ == "__main__":
    unittest.main()
