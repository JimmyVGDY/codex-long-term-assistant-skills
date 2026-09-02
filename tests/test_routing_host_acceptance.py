from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_routing_eval():
    spec = importlib.util.spec_from_file_location(
        "routing_eval", ROOT / "scripts" / "routing-eval.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostRoutingAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_routing_eval()
        cls.cases = cls.module.validate_cases(
            cls.module.load_json(ROOT / "tests" / "skill-routing-cases.json")
        )
        cls.profile = cls.module.validate_host_profile(
            cls.module.load_json(ROOT / "tests" / "host-routing-acceptance-profile.json"),
            cls.cases,
        )
        cls.case_map = {item["id"]: item for item in cls.cases}

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-host-routing-")
        self.evidence_root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_evidence(self, relative: str, content: str) -> str:
        path = self.evidence_root / relative
        path.write_text(content, encoding="utf-8", newline="\n")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def seal_observation(self, item: dict) -> None:
        activated = ",".join(item["activated"]) if item["activated"] else "NONE"
        content = (
            "TASK_ID=%s\nOBSERVED_AT=%s\nACTIVATED_SKILLS=%s\n"
            % (item["task_id"], item["observed_at"], activated)
        )
        item["report_sha256"] = self.write_evidence(item["report_file"], content)

    def valid_results(self) -> dict:
        observations = []
        for index, case_id in enumerate(self.profile["required_case_ids"]):
            case = self.case_map[case_id]
            observations.append({
                "id": case_id,
                "activated": list(case["required"]),
                "task_id": "HOST-TASK-%02d" % index,
                "observed_at": "2026-09-02T%02d:00:00+08:00" % (index + 1),
                "evidence_source": "codex_cli_jsonl",
                "report_file": case_id + ".txt",
                "report_sha256": "",
                "fresh_session": True,
                "explicit_skill_names_in_prompt": False,
                "notes": "",
            })
            self.seal_observation(observations[-1])
        host_readback = (
            "CODEX_VERSION=0.152.1\n"
            "PLUGIN_ID=codex-cross-project-engineering-assistant\n"
            "PLUGIN_VERSION=7.3.0\n"
            "INSTALLED=true\nENABLED=true\n"
        )
        results = {
            "schema_version": 2,
            "observation_kind": "real_codex_host",
            "host": {
                "codex_version": "0.152.1",
                "plugin_id": "codex-cross-project-engineering-assistant",
                "plugin_version": "7.3.0",
                "installed": True,
                "enabled": True,
                "observed_at": "2026-09-02T12:00:00+08:00",
                "platform": "Windows 11",
                "evidence_level": "host_final_report",
                "evidence_method": "fresh_independent_task_final_output",
                "readback_file": "host-readback.txt",
                "readback_sha256": self.write_evidence("host-readback.txt", host_readback),
            },
            "observations": observations,
        }
        return results

    def test_complete_independent_host_observations_pass(self) -> None:
        report = self.module.evaluate_host_acceptance(
            self.cases, self.profile, self.valid_results(), self.evidence_root
        )
        self.assertEqual("PASS", report["status"])
        self.assertEqual(11, report["summary"]["independent_tasks"])
        self.assertEqual("HOST_FINAL_REPORT", report["evidence_scope"])
        self.assertEqual("SHA256_VERIFIED_BYTES", report["evidence_binding"])
        self.assertFalse(report["router_trace_observed"])
        self.assertTrue(all(case["report_file"] for case in report["cases"]))
        self.assertTrue(all(case["observed_at"] for case in report["cases"]))
        self.assertTrue(all(case["evidence_byte_count"] > 0 for case in report["cases"]))

    def test_missing_observation_is_partial_not_pass(self) -> None:
        results = self.valid_results()
        results["observations"].pop()
        report = self.module.evaluate_host_acceptance(
            self.cases, self.profile, results, self.evidence_root
        )
        self.assertEqual("PARTIAL", report["status"])
        self.assertEqual(1, report["summary"]["missing"])

    def test_forbidden_activation_fails(self) -> None:
        results = self.valid_results()
        item = next(
            row for row in results["observations"] if row["id"] == "java-concept-readonly"
        )
        item["activated"].append("engineering-quality-delivery")
        self.seal_observation(item)
        report = self.module.evaluate_host_acceptance(
            self.cases, self.profile, results, self.evidence_root
        )
        self.assertEqual("FAILED", report["status"])
        failed = next(row for row in report["cases"] if row["id"] == "java-concept-readonly")
        self.assertEqual(["engineering-quality-delivery"], failed["activated_forbidden"])

    def test_duplicate_task_or_unverifiable_report_fails_closed(self) -> None:
        duplicate = self.valid_results()
        duplicate["observations"][1]["task_id"] = duplicate["observations"][0]["task_id"]
        with self.assertRaisesRegex(ValueError, "task_id 重复"):
            self.module.evaluate_host_acceptance(
                self.cases, self.profile, duplicate, self.evidence_root
            )

        unverifiable = self.valid_results()
        unverifiable["observations"][0]["report_sha256"] = "not-a-sha256"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.module.evaluate_host_acceptance(
                self.cases, self.profile, unverifiable, self.evidence_root
            )

    def test_explicit_skill_prompt_cannot_count_as_implicit_routing(self) -> None:
        results = deepcopy(self.valid_results())
        results["observations"][0]["explicit_skill_names_in_prompt"] = True
        with self.assertRaisesRegex(ValueError, "explicit_skill_names_in_prompt=false"):
            self.module.evaluate_host_acceptance(
                self.cases, self.profile, results, self.evidence_root
            )

    def test_missing_or_forged_evidence_cannot_pass(self) -> None:
        results = self.valid_results()
        results["host"]["readback_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "内容不匹配"):
            self.module.evaluate_host_acceptance(
                self.cases, self.profile, results, self.evidence_root
            )

        results = self.valid_results()
        (self.evidence_root / results["observations"][0]["report_file"]).unlink()
        with self.assertRaisesRegex(ValueError, "文件不存在"):
            self.module.evaluate_host_acceptance(
                self.cases, self.profile, results, self.evidence_root
            )

    def test_unknown_skill_is_reported_as_failed(self) -> None:
        results = self.valid_results()
        item = next(row for row in results["observations"] if row["id"] == "architecture-document")
        item["activated"].append("invented-skill")
        self.seal_observation(item)
        report = self.module.evaluate_host_acceptance(
            self.cases, self.profile, results, self.evidence_root
        )
        self.assertEqual("FAILED", report["status"])
        failed = next(row for row in report["cases"] if row["id"] == "architecture-document")
        self.assertEqual(["invented-skill"], failed["activated_unrecognized"])

    def test_profile_rejects_nonfinite_pass_rate(self) -> None:
        profile = deepcopy(self.module.load_json(
            ROOT / "tests" / "host-routing-acceptance-profile.json"
        ))
        for value in (float("nan"), float("inf"), float("-inf")):
            profile["minimum_pass_rate"] = value
            with self.assertRaisesRegex(ValueError, "有限数值"):
                self.module.validate_host_profile(profile, self.cases)

    def test_manifest_separates_observation_and_report_schema_versions(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        routing = manifest["routing_regression"]
        self.assertEqual(2, routing["host_observation_schema_version"])
        self.assertEqual(1, routing["host_acceptance_report_schema_version"])


if __name__ == "__main__":
    unittest.main()
