"""中文：针对独立、脚本优先 GPT-6 策略进行契约检查。

English: Focused contract checks for the independent, script-first GPT-6 policy.
"""
from __future__ import annotations

import copy
import unittest

from cp_runtime.g6_flexible_policy import PROFILES, decide, profile_spec
from cp_runtime.routing_contract import RoutingError, ref


def inputs():
    facts = {
        "schema_version": "g6-task-facts/1",
        "identity": {"project_id": "project-a", "repo_fingerprint": ref("repo-a")},
        "task_id": "task-a", "work_item_id": "item-a", "baseline_sha256": "a" * 64,
        "scope_ref": ref("scope-a"), "task_kind": "unknown", "task_kind_source": "unknown",
        "source_refs": [], "missing_evidence": ["quality_card", "historical_samples"],
    }
    budget = {
        "schema_version": "g6-budget-snapshot/1", "ledger_head": "b" * 64,
        "capacity_class": "STRICT", "capacity_units": 32, "capacity_attempts": 10,
        "completed_charged_units": 0, "completed_charged_attempts": 0,
        "inflight_reserved_units": 0, "inflight_reserved_attempts": 0,
        "future_required_hold_units": 0, "future_required_hold_attempts": 0,
        "parallel_limit": 3, "active_calls": 0, "depth_limit": 2, "depth": 0,
        "astra_active": 0, "upward_adjustments_used": 0,
    }
    capability = {"schema_version": "g6-desktop-capability/1",
                  "available_profiles": list(PROFILES), "source_ref": ref("desktop-capability")}
    gates = [{"gate_id": "pre_review", "state": "MISSING_EVIDENCE",
              "affected_action": "none", "source_ref": None}]
    return {"facts": facts, "budget": budget, "capability": capability,
            "gates": gates, "agent_type": "explorer", "task_name": "work_a",
            "message": "Inspect the bounded task.", "decision_time": "2026-10-09T08:00:00Z"}


class G6FlexiblePolicyTests(unittest.TestCase):
    def test_unknown_evidence_uses_executable_default_reproducibly(self):
        args = inputs()
        first = decide(**args)
        second = decide(**copy.deepcopy(args))
        self.assertEqual(first, second)
        self.assertEqual(first["approved_profile"], "g6-sol-medium")
        self.assertEqual(first["decision"], "CONTINUE_DEFAULT")
        self.assertIn("pre_review", first["missing_evidence"])
        self.assertEqual(first["exact_tool_parameters"]["message"], args["message"])

    def test_task_kind_is_labeled_and_scope_counts_do_not_force_escalation(self):
        args = inputs()
        args["facts"].update(task_kind="mechanical", task_kind_source="user_direct")
        args["facts"]["source_refs"] = [ref("user-task-label")]
        self.assertEqual(decide(**args)["approved_profile"], "g6-luna-low")
        args["facts"].update(task_kind="cross_domain_adjudication", task_kind_source="user_direct")
        self.assertEqual(decide(**args)["approved_profile"], "g6-astra-medium")
        args["facts"]["task_kind_source"] = "semantic_proposal"
        self.assertEqual(decide(**args)["approved_profile"], "g6-sol-medium")

    def test_all_nine_profiles_reachable_with_explicit_user_choice(self):
        for name in PROFILES:
            with self.subTest(name=name):
                result = decide(**inputs(), explicit_user_profile=name)
                self.assertEqual(result["approved_profile"], name)
                self.assertEqual(result["planning_units"], profile_spec(name)["planning_units"])

    def test_semantic_adjustment_is_reissued_within_budget_and_ratio(self):
        args = inputs()
        adjustment = {"requested_profile": "g6-sol-high", "source": "model_semantic",
                      "reason": "Need more careful reasoning", "source_ref": None}
        self.assertEqual(decide(**args, adjustment=adjustment)["approved_profile"], "g6-sol-high")
        adjustment["requested_profile"] = "g6-astra-high"
        limited = decide(**args, adjustment=adjustment)
        self.assertEqual(limited["approved_profile"], "g6-sol-medium")
        self.assertIn("ADJUSTMENT_NOT_APPROVED_KEEP_DEFAULT", limited["reason_codes"])
        args["budget"]["upward_adjustments_used"] = 2
        adjustment["requested_profile"] = "g6-sol-high"
        self.assertEqual(decide(**args, adjustment=adjustment)["approved_profile"], "g6-sol-medium")

    def test_user_choice_cannot_be_replaced_by_model_adjustment(self):
        result = decide(**inputs(), explicit_user_profile="g6-luna-medium", adjustment={
            "requested_profile": "g6-sol-high", "source": "model_semantic", "reason": "",
            "source_ref": None})
        self.assertEqual(result["approved_profile"], "g6-luna-medium")

    def test_higher_weight_capability_fallback_within_existing_budget(self):
        args = inputs()
        args["capability"]["available_profiles"] = ["g6-sol-high"]
        result = decide(**args)
        self.assertEqual(result["approved_profile"], "g6-sol-high")
        self.assertIn("CAPABILITY_FALLBACK_HIGHER_WEIGHT", result["reason_codes"])

    def test_missing_gate_continues_but_verified_hard_violation_stops_affected_action(self):
        args = inputs()
        args["gates"].append({"gate_id": "identity_scope", "state": "VERIFIED_HARD_VIOLATION",
                              "affected_action": "spawn_agent", "source_ref": ref("conflict")})
        stopped = decide(**args)
        self.assertEqual(stopped["decision"], "STOP_ACTION")
        self.assertIsNone(stopped["exact_tool_parameters"])
        args["gates"][-1]["affected_action"] = "install"
        self.assertEqual(decide(**args)["decision"], "CONTINUE_DEFAULT")

    def test_budget_or_capability_limits_return_truthful_next_step(self):
        args = inputs()
        args["budget"]["active_calls"] = 3
        self.assertEqual(decide(**args)["decision"], "QUEUE")
        args["budget"]["active_calls"] = 0
        args["budget"].update(completed_charged_units=32, completed_charged_attempts=10)
        self.assertEqual(decide(**args)["decision"], "CONTINUE_LOCAL")
        args = inputs()
        args["capability"]["available_profiles"] = None
        unknown = decide(**args)
        self.assertEqual(unknown["approved_profile"], "g6-sol-medium")
        self.assertIn("CAPABILITY_UNVERIFIED_BOUNDED_ATTEMPT", unknown["reason_codes"])

    def test_corrupt_budget_is_not_treated_as_missing_evidence(self):
        args = inputs()
        args["budget"]["capacity_units"] = 33
        with self.assertRaises(RoutingError):
            decide(**args)


if __name__ == "__main__":
    unittest.main()
