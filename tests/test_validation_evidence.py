from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validation_evidence", ROOT / "scripts" / "validation_evidence.py")
assert SPEC and SPEC.loader
validation_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation_evidence)


class ValidationEvidenceTests(unittest.TestCase):
    def _collect(self, source: str) -> tuple[dict, str, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory(prefix="cp-validation-evidence-")
        directory = Path(temporary.name)
        module = "test_probe_" + uuid.uuid4().hex
        (directory / (module + ".py")).write_text(source, encoding="utf-8")
        return validation_evidence.collect_unittest(directory), module + ".Probe.test_case", temporary

    def test_zero_discovery_and_missing_required_test_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-validation-empty-") as temporary:
            report = validation_evidence.collect_unittest(Path(temporary))
        rows = validation_evidence.evaluate_capabilities((report,), {"probe": ("test_probe.Probe.test_case",)})
        self.assertEqual(0, report["discovered_test_count"])
        self.assertFalse(validation_evidence.suite_passed(report))
        self.assertEqual("NOT_VERIFIED", rows["probe"]["status"])
        self.assertEqual(["REQUIRED_TEST_MISSING"], rows["probe"]["reason_codes"])

    def test_all_skipped_required_tests_cannot_pass(self) -> None:
        report, test_id, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n @unittest.skip('feature disabled')\n def test_case(self): pass\n"
        )
        try:
            row = validation_evidence.evaluate_capabilities((report,), {"probe": (test_id,)})["probe"]
            self.assertEqual("NOT_VERIFIED", row["status"])
            self.assertEqual(["ALL_REQUIRED_TESTS_SKIPPED"], row["reason_codes"])
        finally:
            temporary.cleanup()

    def test_platform_skip_is_explicit_and_not_a_pass(self) -> None:
        report, test_id, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n @unittest.skip('Windows-only probe')\n def test_case(self): pass\n"
        )
        try:
            row = validation_evidence.evaluate_capabilities((report,), {"probe": (test_id,)})["probe"]
            self.assertEqual("NOT_APPLICABLE", row["status"])
            self.assertEqual(["PLATFORM_EXCEPTION"], row["reason_codes"])
            self.assertEqual([test_id], row["platform_exception_test_ids"])
        finally:
            temporary.cleanup()

    def test_error_and_subtest_failure_cannot_pass_and_do_not_expose_body(self) -> None:
        report, test_id, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n def test_case(self):\n  for value in (1, 2):\n   with self.subTest(value=value): self.assertEqual(value, 1, 'SECRET_TEST_BODY')\n  raise RuntimeError('SECRET_ERROR_BODY')\n"
        )
        try:
            row = validation_evidence.evaluate_capabilities((report,), {"probe": (test_id,)})["probe"]
            self.assertEqual("FAIL", row["status"])
            self.assertIn("SUBTEST_FAILURE", row["reason_codes"])
            self.assertIn("ERROR", row["reason_codes"])
            self.assertEqual(["RuntimeError"], report["test_cases"][0]["error_class_codes"])
            self.assertNotIn("SECRET_TEST_BODY", json.dumps(report))
            self.assertNotIn("SECRET_ERROR_BODY", json.dumps(report))
        finally:
            temporary.cleanup()

    def test_error_class_codes_do_not_expose_custom_exception_names_or_messages(self) -> None:
        report, _, temporary = self._collect(
            "import unittest\nclass SECRET_CUSTOM_EXCEPTION_NAME(Exception): pass\nclass Probe(unittest.TestCase):\n def test_case(self): raise SECRET_CUSTOM_EXCEPTION_NAME('SECRET_CUSTOM_EXCEPTION_BODY')\n"
        )
        try:
            self.assertEqual(["UNCLASSIFIED_EXCEPTION"], report["test_cases"][0]["error_class_codes"])
            serialized = json.dumps(report)
            self.assertNotIn("SECRET_CUSTOM_EXCEPTION_NAME", serialized)
            self.assertNotIn("SECRET_CUSTOM_EXCEPTION_BODY", serialized)
        finally:
            temporary.cleanup()

    def test_subtest_exception_keeps_existing_error_class_contract_without_private_text(self) -> None:
        report, test_id, temporary = self._collect(
            "import subprocess, unittest\nclass Probe(unittest.TestCase):\n def test_case(self):\n  with self.subTest(value='SECRET_SUBTEST_PARAMETER'):\n   raise subprocess.TimeoutExpired('SECRET_COMMAND', 30, output='SECRET_OUTPUT', stderr='SECRET_STDERR')\n"
        )
        try:
            case = report["test_cases"][0]
            self.assertEqual(["SUBTEST_FAILURE", "ERROR"], case["statuses"])
            self.assertEqual(["TimeoutExpired"], case["error_class_codes"])
            self.assertEqual(report, validation_evidence.validate_evidence_report(report))
            self.assertFalse(validation_evidence.suite_passed(report))
            self.assertEqual("FAIL", validation_evidence.evaluate_capabilities((report,), {"probe": (test_id,)})["probe"]["status"])
            serialized = json.dumps(report)
            for secret in ("SECRET_SUBTEST_PARAMETER", "SECRET_COMMAND", "SECRET_OUTPUT", "SECRET_STDERR"):
                self.assertNotIn(secret, serialized)
        finally:
            temporary.cleanup()

    def test_error_class_codes_are_optional_for_legacy_reports_and_allowlisted_when_present(self) -> None:
        report, test_id, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n def test_case(self): raise RuntimeError('SECRET_LEGACY_BODY')\n"
        )
        try:
            legacy = dict(report)
            legacy["test_cases"] = [{key: value for key, value in report["test_cases"][0].items() if key != "error_class_codes"}]
            legacy["report_sha256"] = validation_evidence._with_digest(
                {key: value for key, value in legacy.items() if key != "report_sha256"}
            )["report_sha256"]
            self.assertEqual(legacy, validation_evidence.validate_evidence_report(legacy))
            row = validation_evidence.evaluate_capabilities((legacy,), {"probe": (test_id,)})["probe"]
            self.assertEqual("FAIL", row["status"])

            for codes in (["SECRET_CUSTOM_EXCEPTION_NAME"], [{}], [[]], [123], ["RuntimeError", "RuntimeError"]):
                malformed = dict(report)
                malformed["test_cases"] = [dict(report["test_cases"][0], error_class_codes=codes)]
                malformed["report_sha256"] = validation_evidence._with_digest(
                    {key: value for key, value in malformed.items() if key != "report_sha256"}
                )["report_sha256"]
                with self.assertRaisesRegex(validation_evidence.EvidenceError, "error class codes invalid"):
                    validation_evidence.validate_evidence_report(malformed)
        finally:
            temporary.cleanup()

    def test_unexpected_success_cannot_pass(self) -> None:
        report, test_id, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n @unittest.expectedFailure\n def test_case(self): pass\n @unittest.expectedFailure\n def test_expected_failure(self): self.fail('EXPECTED_FAILURE_BODY')\n"
        )
        try:
            row = validation_evidence.evaluate_capabilities((report,), {"probe": (test_id,)})["probe"]
            self.assertEqual("FAIL", row["status"])
            self.assertEqual(["UNEXPECTED_SUCCESS"], row["reason_codes"])
            self.assertEqual(1, report["outcome_counts"]["EXPECTED_FAILURE"])
            self.assertNotIn("EXPECTED_FAILURE_BODY", json.dumps(report))
        finally:
            temporary.cleanup()

    def test_timeout_and_corrupted_report_cannot_be_trusted(self) -> None:
        timeout = validation_evidence.timeout_report("probe", 1)
        row = validation_evidence.evaluate_capabilities((timeout,), {"probe": ("test_probe.Probe.test_case",)})["probe"]
        self.assertEqual("NOT_VERIFIED", row["status"])
        self.assertEqual(["SUITE_NOT_COMPLETED"], row["reason_codes"])
        with tempfile.TemporaryDirectory(prefix="cp-validation-corrupt-") as temporary:
            path = Path(temporary) / "evidence.json"
            path.write_text(json.dumps(timeout | {"report_sha256": "0" * 64}), encoding="utf-8")
            with self.assertRaisesRegex(validation_evidence.EvidenceError, "digest mismatch"):
                validation_evidence.load_evidence_report(path)

    def test_current_source_metadata_and_tampered_report_structure_fail_closed(self) -> None:
        metadata = validation_evidence.package_metadata(ROOT)
        self.assertEqual("codex-cross-project-engineering-assistant", metadata["package"])
        self.assertEqual("7.13.2", metadata["version"])
        self.assertEqual(10, metadata["skill_count"])
        self.assertEqual(7, metadata["reviewer_count"])
        self.assertIs(False, metadata["automatic_self_modification"])
        report, _, temporary = self._collect(
            "import unittest\nclass Probe(unittest.TestCase):\n def test_case(self): pass\n"
        )
        try:
            malformed = dict(report)
            malformed["test_cases"] = [*report["test_cases"], report["test_cases"][0]]
            malformed["discovered_test_count"] = 2
            malformed["executed_test_count"] = 2
            malformed["outcome_counts"] = {"PASS": 2}
            malformed["report_sha256"] = validation_evidence._with_digest({k: v for k, v in malformed.items() if k != "report_sha256"})["report_sha256"]
            with self.assertRaisesRegex(validation_evidence.EvidenceError, "duplicate"):
                validation_evidence.validate_evidence_report(malformed)
            empty = validation_evidence.evaluate_capabilities((report,), {"empty": ()})["empty"]
            self.assertEqual("NOT_VERIFIED", empty["status"])
            self.assertEqual(["REQUIRED_TEST_MAPPING_EMPTY"], empty["reason_codes"])
        finally:
            temporary.cleanup()

    def test_default_mapping_uses_discoverable_exact_test_identifiers(self) -> None:
        self.assertEqual([], validation_evidence.mapping_test_ids_are_loadable(ROOT))
        for required in validation_evidence.CAPABILITY_TEST_MAP.values():
            for test_id in required:
                self.assertNotIn("/", test_id)
                self.assertGreaterEqual(test_id.count("."), 2)

    def test_package_projection_uses_dynamic_source_counts_and_keeps_host_boundary(self) -> None:
        source = (ROOT / "scripts" / "validate-v74.py").read_text(encoding="utf-8")
        cases = json.loads((ROOT / "tests" / "skill-routing-cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertGreater(len(cases), 0)
        self.assertIn('"routing_case_count"', source)
        self.assertIn('"PASS (%d cases)" % metadata["routing_case_count"]', source)
        self.assertNotIn("PASS (45 cases)", source)
        self.assertIn('"routing_host_observation": "NOT_EVALUATED (package-only validation)"', source)


if __name__ == "__main__":
    unittest.main()
