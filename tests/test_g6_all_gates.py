"""中文：新策略的每个门禁都有明确的缺证据继续路径。

English: Every new-policy gate has an explicit missing-evidence continuation path.
"""
from __future__ import annotations

import unittest

from cp_runtime.g6_delivery_v1 import evaluate_delivery
from cp_runtime.g6_gate_catalog import CATALOG, complete_gates, stage_decision
from cp_runtime.routing_contract import ref


class G6AllGatesTests(unittest.TestCase):
    def test_catalog_has_complete_operational_entries_and_missing_path(self):
        for name, entry in CATALOG.items():
            with self.subTest(name=name):
                self.assertEqual(set(entry), {"entrypoint", "consumers", "normal_rule",
                                              "missing_evidence_default",
                                              "known_violation_action", "next_action"})
                self.assertTrue(entry["consumers"])
                self.assertTrue(entry["next_action"])
                result = stage_decision(name, None, action="spawn_agent")
                self.assertEqual(result["decision"], "CONTINUE_DEGRADED")
                self.assertEqual(result["gate_state"], "MISSING_EVIDENCE")
                self.assertNotEqual(result["next_action"], "disable_gate")
        all_missing = complete_gates([])
        self.assertEqual(len(all_missing), len(CATALOG))
        self.assertTrue(all(item["state"] == "MISSING_EVIDENCE" for item in all_missing))
        unproved = complete_gates([{"gate_id": "post_review", "state": "PASS",
                                    "affected_action": "none", "source_ref": None}])
        self.assertEqual(next(item for item in unproved if item["gate_id"] == "post_review")
                         ["state"], "MISSING_EVIDENCE")

    def test_known_hard_violation_restricts_only_affected_action(self):
        gate = {"gate_id": "validation", "state": "VERIFIED_HARD_VIOLATION",
                "affected_action": "install", "source_ref": ref("failed-safety-check")}
        self.assertEqual(stage_decision("validation", gate, action="install")["decision"], "STOP_ACTION")
        self.assertEqual(stage_decision("validation", gate, action="write")["decision"], "CONTINUE_DEFAULT")

    def test_delivery_keeps_missing_review_and_readback_unverified(self):
        baseline = "a" * 64
        required = [{"check_id": "required-build", "required": True, "exit_code": 0,
                     "source_ref": ref("build-output"), "baseline_sha256": baseline}]
        result = evaluate_delivery(checks=required, baseline_sha256=baseline,
                                   installed=True, installed_readback_ref=None)
        self.assertEqual(result["status"], "INSTALLED_EFFECT_UNVERIFIED")
        self.assertFalse(result["independent_review_verified"])
        self.assertFalse(result["installed_readback_verified"])

    def test_failed_required_check_blocks_release_but_unknown_keeps_local_result(self):
        baseline = "a" * 64
        check = {"check_id": "required-build", "required": True, "exit_code": 1,
                 "source_ref": ref("failed-build"), "baseline_sha256": baseline}
        failed = evaluate_delivery(checks=[check], baseline_sha256=baseline, action="install")
        self.assertEqual(failed["status"], "ACTION_RESTRICTED")
        check["exit_code"] = None
        check["source_ref"] = None
        unknown = evaluate_delivery(checks=[check], baseline_sha256=baseline, action="install")
        self.assertEqual(unknown["status"], "LOCAL_RESULT_UNVERIFIED")
        self.assertNotEqual(unknown["gate_decisions"][0]["decision"], "STOP_ACTION")

    def test_confirmed_review_hard_gate_overrides_passing_checks_for_its_action(self):
        baseline = "a" * 64
        check = {"check_id": "required-build", "required": True, "exit_code": 0,
                 "source_ref": ref("build-pass"), "baseline_sha256": baseline}
        confirmed = {"gate_id": "post_review", "state": "VERIFIED_HARD_VIOLATION",
                     "affected_action": "publish", "source_ref": ref("adjudicated-review-block")}
        result = evaluate_delivery(checks=[check], baseline_sha256=baseline,
                                   post_review=confirmed, action="publish")
        self.assertEqual(result["status"], "ACTION_RESTRICTED")
        self.assertEqual(result["restricted_action"], "publish")
        self.assertNotEqual(result["next_action"], "continue_authorized_delivery")
        other = evaluate_delivery(checks=[check], baseline_sha256=baseline,
                                  post_review=confirmed, action="install")
        self.assertNotEqual(other["status"], "ACTION_RESTRICTED")


if __name__ == "__main__":
    unittest.main()
