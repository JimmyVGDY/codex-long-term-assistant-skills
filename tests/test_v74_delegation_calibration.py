from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import (  # noqa: E402
    DelegationBudgetError, initialize_budget, mark_completed, mark_started,
    record_decision, reserve_budget,
)
from cp_runtime.delegation_calibration import (  # noqa: E402
    append_sample, build_pending_sample, finalize_sample, load_samples, offline_replay,
)

FINGERPRINT = "sha256:" + "c" * 64
EVIDENCE = "sha256:" + "d" * 64


class DelegationCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = self.root / "budget.jsonl"
        self.samples = self.root / "samples.jsonl"
        initialize_budget(self.ledger, budget_id="CAL-BUDGET", task_id="CAL-TASK", project_id="cal-project",
                          repo_fingerprint=FINGERPRINT, budget_class="STRICT", default_model_profile="luna-low")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def completed(self, key: str, role: str, profile: str, actual: str | None = None) -> str:
        record_decision(self.ledger, dispatch_key=key, decision="DELEGATE", role=role,
                        requested_profile=profile, reason_code="SEMANTIC_COMPLEXITY",
                        responsibility="schema", difficulty="HIGH", risk_domain="DATA", context_size="MEDIUM")
        reservation = reserve_budget(self.ledger, dispatch_key=key, host_dispatch_id="tool-" + key,
                                     requested_profile=profile, request_basis="explicit-request", role=role)
        mark_started(self.ledger, reservation_id=reservation["reservation_id"], agent_id="agent-" + key,
                     actual_profile=actual or "",
                     runtime_evidence="host-attested-hook-payload" if actual else "unavailable")
        mark_completed(self.ledger, reservation_id=reservation["reservation_id"], outcome="PASS")
        return reservation["reservation_id"]

    def test_child_report_stays_pending_until_parent_finalizes(self) -> None:
        reservation_id = self.completed("review-one", "reviewer", "luna-low")
        metrics = {"accepted_findings": 1, "repaired_findings": 1, "duplicate_findings": 0,
                   "missed_findings": 0, "regressions_prevented": 1}
        pending = build_pending_sample(self.ledger, reservation_id, metrics)
        self.assertFalse(pending["calibration_finalized"])
        with self.assertRaises(DelegationBudgetError):
            finalize_sample(pending, finalized_by="child:reviewer", evidence_refs=[EVIDENCE])
        final = finalize_sample(pending, finalized_by="parent:coordinator",
                                evidence_refs=[pending["reservation_completion_ref"], EVIDENCE], duration_ms=10)
        append_sample(self.samples, final, ledger_path=self.ledger)
        self.assertTrue(load_samples(self.samples, ledger_path=self.ledger)[0]["calibration_finalized"])

    def test_role_specific_metrics_are_strict(self) -> None:
        reservation_id = self.completed("explore-one", "explorer", "luna-low")
        with self.assertRaises(DelegationBudgetError):
            build_pending_sample(self.ledger, reservation_id, {"accepted_findings": 1})
        pending = build_pending_sample(self.ledger, reservation_id,
                                       {"evidence_adopted": 1, "questions_resolved": 1, "duplicate_explorations": 0})
        self.assertGreater(pending["value_score"], 0)
        with self.assertRaises(DelegationBudgetError):
            build_pending_sample(self.ledger, reservation_id,
                                 {"evidence_adopted": 1, "questions_resolved": 1, "duplicate_explorations": 0},
                                 source="free-form-child-notes")

    def test_finalization_rejects_malformed_hash_and_tampered_score(self) -> None:
        reservation_id = self.completed("worker-validation", "worker", "luna-low")
        pending = build_pending_sample(
            self.ledger, reservation_id,
            {"deliveries_accepted": 1, "validations_passed": 1, "rework_rounds": 0, "rollbacks": 0},
        )
        with self.assertRaises(DelegationBudgetError):
            finalize_sample(pending, finalized_by="parent:root", evidence_refs=["sha256:" + "z" * 64])
        final = finalize_sample(pending, finalized_by="parent:root",
                                evidence_refs=[pending["reservation_completion_ref"], EVIDENCE])
        final["value_score"] += 1
        with self.assertRaises(DelegationBudgetError):
            append_sample(self.samples, final, ledger_path=self.ledger)

    def test_sample_must_match_completed_budget_reservation_and_metric_bounds(self) -> None:
        reservation_id = self.completed("bound-worker", "worker", "luna-low")
        with self.assertRaises(DelegationBudgetError):
            build_pending_sample(
                self.ledger, reservation_id,
                {"deliveries_accepted": 1001, "validations_passed": 0, "rework_rounds": 0, "rollbacks": 0},
            )
        pending = build_pending_sample(
            self.ledger, reservation_id,
            {"deliveries_accepted": 1, "validations_passed": 1, "rework_rounds": 0, "rollbacks": 0},
        )
        final = finalize_sample(pending, finalized_by="parent:root",
                                evidence_refs=[pending["reservation_completion_ref"], EVIDENCE])
        final["reservation_id"] = "DBR_forged"
        with self.assertRaises(DelegationBudgetError):
            append_sample(self.samples, final, ledger_path=self.ledger)

    def test_unverified_runtime_and_insufficient_data_cannot_change_route(self) -> None:
        reservation_id = self.completed("worker-one", "worker", "luna-low")
        pending = build_pending_sample(self.ledger, reservation_id,
                                       {"deliveries_accepted": 1, "validations_passed": 1, "rework_rounds": 0, "rollbacks": 0})
        final = finalize_sample(pending, finalized_by="parent:root",
                                evidence_refs=[pending["reservation_completion_ref"], EVIDENCE])
        proposal = offline_replay([final], ledger_path=self.ledger, minimum_samples_per_profile=1)
        self.assertEqual("NONE", proposal["execution_authorization"])
        self.assertEqual(0, proposal["sample_count"])
        self.assertFalse(proposal["automatic_changes_applied"])

    def test_adjacent_tier_replay_requires_minimum_samples_and_never_executes(self) -> None:
        records = []
        for index, profile in enumerate(("luna-low", "luna-medium"), 1):
            reservation_id = self.completed("review-%d" % index, "reviewer", profile, actual=profile)
            pending = build_pending_sample(self.ledger, reservation_id,
                                           {"accepted_findings": index, "repaired_findings": index,
                                            "duplicate_findings": 0, "missed_findings": 0,
                                            "regressions_prevented": index})
            records.append(finalize_sample(
                pending, finalized_by="parent:root",
                evidence_refs=[pending["reservation_completion_ref"], EVIDENCE],
            ))
        insufficient = offline_replay(records, ledger_path=self.ledger, minimum_samples_per_profile=2)
        pair = next(item for item in insufficient["comparisons"]
                    if item["lower_profile"] == "luna-low" and item["higher_profile"] == "luna-medium")
        self.assertFalse(pair["eligible"])
        self.assertEqual("NO_CHANGE_INSUFFICIENT_DATA", pair["recommendation"])
        eligible = offline_replay(records, ledger_path=self.ledger, minimum_samples_per_profile=1)
        pair = next(item for item in eligible["comparisons"]
                    if item["lower_profile"] == "luna-low" and item["higher_profile"] == "luna-medium")
        self.assertTrue(pair["eligible"])
        self.assertEqual("NONE", eligible["execution_authorization"])
        self.assertFalse(eligible["automatic_changes_applied"])


if __name__ == "__main__":
    unittest.main()
