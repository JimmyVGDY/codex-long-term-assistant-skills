from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.evolution.observation import observe_project

CONTROLLER = ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_controller.py"
PACKET = ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_packet.py"


class ModelRoutingCalibrationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="model-routing-gates-")
        self.root = Path(self.temporary.name)
        self.review = self.root / "review"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(self, script: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *args], cwd=ROOT, text=True,
            encoding="utf-8", errors="replace", capture_output=True,
        )
        if ok:
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        else:
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def init_and_dispatch(self, minimum: str = "luna-medium") -> None:
        self.run_tool(CONTROLLER, "init", "--review-dir", str(self.review),
                      "--boundary-id", "boundary-one", "--task-id", "task-one")
        self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review),
                      "--phase", "post", "--decision", "DELEGATE",
                      "--reason-code", "RISK_REVIEW", "--reason", "需要独立复审")
        self.run_tool(CONTROLLER, "plan", "--review-dir", str(self.review),
                      "--phase", "post", "--depth", "1", "--reviewers", "reviewer-one",
                      "--purpose", "校准契约复审", "--effort-tier", "deep")
        self.run_tool(CONTROLLER, "dispatch", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--scope", "契约", "--model-profile", "terra-medium",
                      "--minimum-acceptable-profile", minimum)

    def write_result(self, runtime_profile: str) -> Path:
        runtime = {
            "luna-low": ("gpt-5.6-luna", "low"),
            "luna-medium": ("gpt-5.6-luna", "medium"),
            "terra-medium": ("gpt-5.6-terra", "medium"),
        }[runtime_profile]
        result = {
            "schema_version": 3,
            "result_id": "RVR_" + hashlib.sha256(b"boundary-one|task-one|post|1|reviewer-one|").hexdigest(),
            "reviewer": "reviewer-one", "task_id": "task-one", "review_phase": "post", "review_round": 1,
            "boundary_id": "boundary-one", "packet_sha256": "", "status": "pass",
            "isolation_level": "logical-readonly",
            "model_assignment": {
                "requested_profile": "terra-medium", "requested_model": "gpt-5.6-terra",
                "requested_reasoning_effort": "medium", "minimum_acceptable_profile": "luna-medium",
                "runtime_model": runtime[0], "runtime_reasoning_effort": runtime[1],
                "status": "unverified", "runtime_evidence_level": "declared",
                "runtime_evidence_source": "reviewer-result",
            },
            "task_difficulty": "HIGH", "duration_ms": 12, "estimated_cost_units": 4,
            "cost_formula_version": "profile-weight-v1", "calibration_finalized": False,
            "accepted": 0, "rejected": 0, "duplicate": 0, "repaired": 0,
            "regressions_prevented": 0, "checked_scope": [], "findings": [],
            "unverified_items": [], "summary": "完成",
        }
        path = self.root / (runtime_profile + ".json")
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return path

    def state(self) -> dict:
        return json.loads((self.review / "review-state.json").read_text(encoding="utf-8"))

    def raw_controller(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *args], cwd=ROOT, text=True,
            encoding="utf-8", errors="replace", capture_output=True,
        )

    def test_minimum_profile_allows_declared_acceptable_fallback_and_projects_cost(self) -> None:
        self.init_and_dispatch()
        result_path = self.write_result("luna-medium")
        self.run_tool(CONTROLLER, "result", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--status", "pass", "--summary", "通过", "--result-file", str(result_path))
        recorded = self.state()["phases"]["post"]["rounds"]["1"]["results"]["reviewer-one"]
        self.assertEqual("fallback_acceptable", recorded["model_assignment"]["status"])
        self.assertEqual("declared", recorded["model_assignment"]["runtime_evidence_level"])
        ledger = [json.loads(line) for line in (self.review / "review-results.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(1, len(ledger))
        projected = ledger[0]["reviewer_results"][0]
        self.assertEqual(4.0, projected["estimated_cost_units"])
        self.assertEqual("terra-medium", projected["requested_model_profile"])
        self.assertEqual("luna-medium", projected["declared_runtime_profile"])
        self.assertEqual("terra-medium", projected["cost_basis_profile"])
        self.assertFalse(projected["calibration_finalized"])
        self.run_tool(CONTROLLER, "finalize-calibration", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--finalized-by", "primary-coordinator", "--accepted", "1", "--rejected", "0",
                      "--duplicate", "0", "--repaired", "1", "--regressions-prevented", "1",
                      "--evidence", "tests/test_model_routing_calibration_gates.py")
        finalized = json.loads((self.review / "review-results.jsonl").read_text(encoding="utf-8"))
        finalized_result = finalized["reviewer_results"][0]
        self.assertTrue(finalized_result["calibration_finalized"])
        self.assertEqual(1, finalized_result["repaired"])
        self.assertEqual("primary-coordinator", finalized_result["calibration_finalization"]["finalized_by"])
        self.run_tool(CONTROLLER, "finalize-calibration", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--finalized-by", "primary-coordinator", "--accepted", "1", "--rejected", "0",
                      "--duplicate", "0", "--repaired", "1", "--regressions-prevented", "1",
                      "--evidence", "duplicate", ok=False)
        (self.review / "review-results.jsonl").write_text("{}\n", encoding="utf-8")
        self.run_tool(CONTROLLER, "validate", "--review-dir", str(self.review), ok=False)
        self.run_tool(CONTROLLER, "sync-calibration", "--review-dir", str(self.review))
        self.run_tool(CONTROLLER, "validate", "--review-dir", str(self.review))

    def test_underpowered_pass_is_rejected_without_state_or_ledger_side_effects(self) -> None:
        self.init_and_dispatch()
        result_path = self.write_result("luna-low")
        before = (self.review / "review-state.json").read_bytes()
        self.run_tool(CONTROLLER, "result", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--status", "pass", "--summary", "错误通过", "--result-file", str(result_path), ok=False)
        self.assertEqual(before, (self.review / "review-state.json").read_bytes())
        self.assertFalse((self.review / "review-results.jsonl").exists())
        incomplete = json.loads(result_path.read_text(encoding="utf-8"))
        incomplete["status"] = "incomplete"
        result_path.write_text(json.dumps(incomplete, ensure_ascii=False), encoding="utf-8")
        self.run_tool(CONTROLLER, "result", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--status", "incomplete", "--summary", "档位不足", "--result-file", str(result_path))
        self.assertEqual(1, self.state()["counters"]["underpowered_results"])
        self.run_tool(CONTROLLER, "merge", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--summary", "不应归并", ok=False)
        self.run_tool(CONTROLLER, "close", "--review-dir", str(self.review),
                      "--conclusion", "逻辑只读复审完成，无阻塞项", ok=False)

    def test_nested_or_non_string_regression_evidence_is_rejected_without_side_effects(self) -> None:
        self.init_and_dispatch()
        result_path = self.write_result("terra-medium")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        finding = {
            "id": "F-1", "dimension": "data-contract", "severity": "BLOCKING",
            "evidence_level": "LOGICAL", "blocking": True, "summary": "契约错误",
            "location": "review_controller.py", "root_cause_group": "schema-validation",
            "required_validation": ["targeted-test"], "disposition": "ACCEPTED",
            "adoption_reason": "DATA_CONTRACT", "repaired": False,
            "regression_prevented": False, "regression_evidence": [],
        }
        result["findings"] = [finding]
        before = (self.review / "review-state.json").read_bytes()
        for invalid_evidence in ([{"raw_prompt": "secret"}], [{"reference": "not-a-string"}]):
            with self.subTest(evidence=invalid_evidence):
                result["findings"][0]["regression_evidence"] = invalid_evidence
                result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                self.run_tool(CONTROLLER, "result", "--review-dir", str(self.review),
                              "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                              "--status", "pass", "--summary", "不应写入",
                              "--result-file", str(result_path), ok=False)
                self.assertEqual(before, (self.review / "review-state.json").read_bytes())
                self.assertFalse((self.review / "review-results.jsonl").exists())

    def test_inline_decision_is_append_only_budget_free_and_requires_evidenced_redecision(self) -> None:
        self.run_tool(CONTROLLER, "init", "--review-dir", str(self.review), "--boundary-id", "inline-boundary")
        self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "pre",
                      "--decision", "INLINE", "--reason-code", "TRIVIAL", "--reason", "简单本地检查")
        inline_state = self.state()
        self.assertEqual(0, inline_state["counters"]["total_reviewers"])
        before = (self.review / "review-state.json").read_bytes()
        self.run_tool(CONTROLLER, "plan", "--review-dir", str(self.review), "--phase", "pre",
                      "--depth", "1", "--reviewers", "r1", "--purpose", "绕过", ok=False)
        self.assertEqual(before, (self.review / "review-state.json").read_bytes())
        decision_id = inline_state["routing_decisions"]["pre"][-1]["decision_id"]
        self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "pre",
                      "--decision", "DELEGATE", "--reason-code", "NEW_RISK", "--reason", "发现新风险",
                      "--supersedes", decision_id, "--change-reason", "风险边界变化", ok=False)
        self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "pre",
                      "--decision", "DELEGATE", "--reason-code", "NEW_RISK", "--reason", "发现新风险",
                      "--supersedes", decision_id, "--change-reason", "风险边界变化",
                      "--evidence", "tests/new-risk")
        self.run_tool(CONTROLLER, "plan", "--review-dir", str(self.review), "--phase", "pre",
                      "--depth", "1", "--reviewers", "r1", "--purpose", "风险复审")
        latest = self.state()["routing_decisions"]["pre"][-1]["decision_id"]
        self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "pre",
                      "--decision", "INLINE", "--reason-code", "REVERT", "--reason", "不再需要",
                      "--supersedes", latest, "--change-reason", "尝试改判", "--evidence", "x", ok=False)

    def test_new_state_requires_route_but_migrated_v4_keeps_legacy_plan_path(self) -> None:
        self.run_tool(CONTROLLER, "init", "--review-dir", str(self.review), "--boundary-id", "route-required")
        self.run_tool(CONTROLLER, "plan", "--review-dir", str(self.review), "--phase", "post",
                      "--depth", "1", "--reviewers", "r1", "--purpose", "missing route", ok=False)
        legacy = self.state()
        legacy["schema_version"] = 4
        legacy.pop("routing_decision_required", None)
        legacy.pop("routing_decisions", None)
        (self.review / "review-state.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        self.run_tool(CONTROLLER, "plan", "--review-dir", str(self.review), "--phase", "post",
                      "--depth", "1", "--reviewers", "r1", "--purpose", "legacy path")

    def test_v4_fallback_migrates_conservatively_to_underpowered(self) -> None:
        self.init_and_dispatch()
        result_path = self.write_result("luna-medium")
        self.run_tool(CONTROLLER, "result", "--review-dir", str(self.review),
                      "--phase", "post", "--round", "1", "--reviewer", "reviewer-one",
                      "--status", "pass", "--summary", "legacy result", "--result-file", str(result_path))
        legacy = self.state()
        legacy["schema_version"] = 4
        legacy.pop("task_id", None)
        legacy.pop("routing_decision_required", None)
        legacy.pop("routing_decisions", None)
        legacy["counters"].pop("underpowered_results", None)
        round_data = legacy["phases"]["post"]["rounds"]["1"]
        round_data["dispatch"]["reviewer-one"].pop("minimum_acceptable_profile", None)
        assignment = round_data["results"]["reviewer-one"]["model_assignment"]
        assignment.pop("minimum_acceptable_profile", None)
        assignment.pop("runtime_evidence_level", None)
        assignment.pop("runtime_evidence_source", None)
        assignment["status"] = "fallback"
        round_data["results"]["reviewer-one"]["status"] = "pass"
        (self.review / "review-state.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        self.run_tool(CONTROLLER, "close", "--review-dir", str(self.review),
                      "--conclusion", "有阻塞问题")
        migrated = self.state()
        result = migrated["phases"]["post"]["rounds"]["1"]["results"]["reviewer-one"]
        self.assertEqual("underpowered", result["model_assignment"]["status"])
        self.assertEqual("incomplete", result["status"])
        self.assertEqual("terra-medium", result["model_assignment"]["minimum_acceptable_profile"])

    def test_route_plan_dispatch_concurrency_preserves_one_valid_transition(self) -> None:
        self.run_tool(CONTROLLER, "init", "--review-dir", str(self.review), "--boundary-id", "concurrent")
        first_commands = [
            ("route", "--review-dir", str(self.review), "--phase", "post", "--decision", decision,
             "--reason-code", "FIRST", "--reason", "并发首决策")
            for decision in ("INLINE", "DELEGATE")
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = list(pool.map(lambda command: self.raw_controller(*command), first_commands))
        self.assertEqual(1, sum(item.returncode == 0 for item in first))
        self.run_tool(CONTROLLER, "validate", "--review-dir", str(self.review))

        latest = self.state()["routing_decisions"]["post"][-1]
        if latest["decision"] == "INLINE":
            self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "post",
                          "--decision", "DELEGATE", "--reason-code", "READY", "--reason", "准备复审",
                          "--supersedes", latest["decision_id"], "--change-reason", "增加行为改动",
                          "--evidence", "tests/concurrency")
        delegate = self.state()["routing_decisions"]["post"][-1]["decision_id"]
        plan_command = ("plan", "--review-dir", str(self.review), "--phase", "post", "--depth", "1",
                        "--reviewers", "r1", "--purpose", "并发计划")
        route_command = ("route", "--review-dir", str(self.review), "--phase", "post", "--decision", "INLINE",
                         "--reason-code", "NO_LONGER", "--reason", "并发改判", "--supersedes", delegate,
                         "--change-reason", "新证据", "--evidence", "tests/new-evidence")
        with ThreadPoolExecutor(max_workers=2) as pool:
            second = list(pool.map(lambda command: self.raw_controller(*command), (plan_command, route_command)))
        self.assertEqual(1, sum(item.returncode == 0 for item in second))
        self.run_tool(CONTROLLER, "validate", "--review-dir", str(self.review))

        state = self.state()
        if not state["phases"]["post"]["rounds"]:
            latest = state["routing_decisions"]["post"][-1]
            self.run_tool(CONTROLLER, "route", "--review-dir", str(self.review), "--phase", "post",
                          "--decision", "DELEGATE", "--reason-code", "RESTORE", "--reason", "恢复复审",
                          "--supersedes", latest["decision_id"], "--change-reason", "执行并发派发验证",
                          "--evidence", "tests/dispatch-race")
            self.run_tool(CONTROLLER, *plan_command)
        latest = self.state()["routing_decisions"]["post"][-1]["decision_id"]
        dispatch_command = ("dispatch", "--review-dir", str(self.review), "--phase", "post", "--round", "1",
                            "--reviewer", "r1", "--scope", "并发门禁")
        late_route_command = ("route", "--review-dir", str(self.review), "--phase", "post", "--decision", "INLINE",
                              "--reason-code", "TOO_LATE", "--reason", "轮次后改判", "--supersedes", latest,
                              "--change-reason", "不应成功", "--evidence", "tests/late")
        with ThreadPoolExecutor(max_workers=2) as pool:
            third = list(pool.map(lambda command: self.raw_controller(*command), (dispatch_command, late_route_command)))
        success_count = sum(item.returncode == 0 for item in third)
        self.assertLessEqual(success_count, 1)
        self.run_tool(CONTROLLER, "validate", "--review-dir", str(self.review))
        if success_count == 0:
            self.run_tool(CONTROLLER, *dispatch_command)
        self.assertEqual(["r1"], self.state()["phases"]["post"]["rounds"]["1"]["active"])

    def test_result_template_v3_and_v2_validation_compatibility(self) -> None:
        packet_dir = self.root / "packet"
        packet_dir.mkdir()
        manifest = {"schema_version": 3, "boundary_id": "packet-boundary",
                    "packet_sha256": "b" * 64, "default_model_profile": "luna-medium"}
        (packet_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        output = self.root / "result-v3.json"
        self.run_tool(PACKET, "result-template", "--packet-dir", str(packet_dir),
                      "--reviewer", "r1", "--task-id", "task-v3", "--review-round", "2",
                      "--task-difficulty", "MEDIUM", "--model-profile", "terra-medium",
                      "--minimum-acceptable-profile", "luna-medium", "--output", str(output))
        value = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(3, value["schema_version"])
        self.assertEqual("post", value["review_phase"])
        self.assertEqual(4.0, value["estimated_cost_units"])
        self.assertEqual("luna-medium", value["model_assignment"]["minimum_acceptable_profile"])
        self.run_tool(PACKET, "validate-result", "--packet-dir", str(packet_dir),
                      "--result-file", str(output), "--reviewer", "r1")
        invalid_finalized = dict(value)
        invalid_finalized["calibration_finalized"] = True
        invalid_path = self.root / "invalid-finalized.json"
        invalid_path.write_text(json.dumps(invalid_finalized), encoding="utf-8")
        self.run_tool(PACKET, "validate-result", "--packet-dir", str(packet_dir),
                      "--result-file", str(invalid_path), "--reviewer", "r1", ok=False)
        unexpected = dict(value)
        unexpected["prompt_text"] = "must not persist"
        unexpected_path = self.root / "unexpected-field.json"
        unexpected_path.write_text(json.dumps(unexpected), encoding="utf-8")
        self.run_tool(PACKET, "validate-result", "--packet-dir", str(packet_dir),
                      "--result-file", str(unexpected_path), "--reviewer", "r1", ok=False)

        legacy = {key: value[key] for key in (
            "result_id", "reviewer", "boundary_id", "packet_sha256", "status", "isolation_level",
            "checked_scope", "findings", "unverified_items", "summary"
        )}
        legacy["schema_version"] = 2
        legacy["result_id"] = "RVR_" + hashlib.sha256(
            ("packet-boundary|r1|" + "b" * 64).encode("utf-8")
        ).hexdigest()
        legacy["model_assignment"] = {
            "requested_profile": "terra-medium", "requested_model": "gpt-5.6-terra",
            "requested_reasoning_effort": "medium", "runtime_model": "",
            "runtime_reasoning_effort": "", "status": "unverified",
        }
        legacy_path = self.root / "legacy-v2.json"
        legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
        self.run_tool(PACKET, "validate-result", "--packet-dir", str(packet_dir),
                      "--result-file", str(legacy_path), "--reviewer", "r1")

    def test_observation_keeps_unknown_cost_and_unfinalized_attribution_out_of_yield(self) -> None:
        project = self.root / "project"
        source = project / "review" / "review-results.jsonl"
        source.parent.mkdir(parents=True)
        rows = []
        for index in range(8):
            result = {
                "reviewer": "calibration-reviewer", "result_id": "RR-%d" % index,
                "task_difficulty": "HIGH", "model_profile": "terra-medium",
                "accepted": 3, "rejected": 0, "repaired": 2,
                "calibration_finalized": False,
                "findings": [{"severity": "HIGH", "disposition": "REPAIRED",
                              "adoption_reason": "CORRECTNESS"}],
            }
            if index < 4:
                result.update(estimated_cost_units=4, cost_formula_version="profile-weight-v1")
            rows.append({"record_id": "R-%d" % index, "task_id": "TASK-%d" % index,
                         "timestamp": "2026-08-%02dT00:00:00+00:00" % (index + 1),
                         "reviewer_results": [result]})
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        stats = observe_project("project", project).metrics["reviewer_stats"]["calibration-reviewer"]
        self.assertEqual(4, stats["known_cost_invocation_count"])
        self.assertEqual(4, stats["unknown_cost_invocation_count"])
        self.assertEqual(0.5, stats["cost_coverage"])
        self.assertEqual(8, stats["unfinalized_invocation_count"])
        self.assertEqual(0, stats["accepted"])
        self.assertIsNone(stats["benefit_proxy"])
        self.assertEqual("INSUFFICIENT_DATA", stats["calibration_status"])
        self.assertEqual({"cost-basis:terra-medium|HIGH": 8}, stats["profile_difficulty_distribution"])

    def test_observation_excludes_unfinalized_cost_from_benefit_denominator(self) -> None:
        project = self.root / "mixed-finalization-project"
        source = project / "review" / "review-results.jsonl"
        source.parent.mkdir(parents=True)
        rows = []
        for index in range(10):
            finalized = index < 8
            result = {
                "reviewer": "mixed-reviewer", "result_id": "MIXED-%d" % index,
                "task_difficulty": "HIGH", "model_profile": "terra-medium",
                "estimated_cost_units": 1 if finalized else 100,
                "cost_formula_version": "profile-weight-v1",
                "accepted": 1 if finalized else 0, "rejected": 0,
                "repaired": 1 if finalized else 0,
                "calibration_finalized": finalized,
                "findings": [{"severity": "HIGH", "disposition": "ACCEPTED" if finalized else "PENDING",
                              "adoption_reason": "CORRECTNESS"}],
            }
            rows.append({"record_id": "MIXED-R-%d" % index, "task_id": "MIXED-TASK-%d" % index,
                         "timestamp": "2026-08-%02dT00:00:00+00:00" % (index + 1),
                         "reviewer_results": [result]})
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        stats = observe_project("mixed-finalization-project", project).metrics["reviewer_stats"]["mixed-reviewer"]
        self.assertEqual(208.0, stats["estimated_cost_units"])
        self.assertEqual(8.0, stats["finalized_estimated_cost_units"])
        self.assertEqual(8, stats["finalized_known_cost_invocation_count"])
        self.assertEqual(1.0, stats["benefit_proxy"])
        self.assertEqual(1.0, stats["cost_per_repaired"])


if __name__ == "__main__":
    unittest.main()
