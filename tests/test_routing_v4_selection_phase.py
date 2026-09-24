"""中文：选择与跨阶段可行性；费用/资格为构造的统计夹具。

English: Selection and cross-phase feasibility using invented evaluation data.
"""
from __future__ import annotations

import copy
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.routing_contract import RoutingError, policy_digest, ref, resource_need
from cp_runtime.routing_cards import build_bundle
from cp_runtime.routing_phase_plan import (capacity_after_choice, feasible_witness,
                                          validate_plan, validate_revision)
from cp_runtime.routing_v4 import combine_cards, select, snapshot_references
import v4_fixtures as fx


def option(profile, units):
    return {"profile_id": profile, "qualification_ref": ref("synthetic-quality"),
            "cost_ref": ref("synthetic-cost"), "resources": resource_need(profile, units)}


def slot(name, options, *, role="cp_review_data_contract", phase="post"):
    return {"slot_id": name, "scenario": {**copy.deepcopy(fx.SCENARIO), "role": role, "phase": phase},
            "condition": "repair-after-post" if phase == "repair" else "always",
            "depends_on": [], "status": "PENDING", "options": options,
            "independence_required": True,
            "active_reservation_ref": "", "accepted_result_ref": "", "release_evidence_ref": ""}


def plan(slots):
    return {"schema_version": "phase-plan/1", "plan_id": "synthetic-plan", "revision": 1,
            "identity": fx.IDENTITY, "slots": slots}


def capacity(units=100, astra=2, high=1):
    return {"units": units, "attempts": 6, "astra_attempts": astra, "astra_high_attempts": high}


def prepared(bundle):
    cards = combine_cards([bundle], [ref("synthetic-publication")], declared_identity=fx.IDENTITY)
    qualities = {item["profile_id"]: item for item in cards["qualification"]}
    options = [
        {"profile_id": cost["profile_id"], "cost_ref": ref(cost),
         "qualification_ref": ref(qualities[cost["profile_id"]]),
         "resources": resource_need(cost["profile_id"], cost["reserve_units"])}
        for cost in cards["costs"]
    ]
    snapshot = {
        "schema_version": "routing-input/1", "identity": fx.IDENTITY, "policy_digest": policy_digest(),
        "execution_mode": "PRODUCTION", "cards": cards, "now": fx.NOW,
        "capability": {"schema_version": "desktop-capability/1", "host_surface": "codex-desktop",
                       "source": "host-tool-metadata", "root_session_ref": ref("synthetic-session"),
                       "revision": 1, "available_profiles": list(qualities),
                       "created_at": fx.NOW, "expires_at": fx.EXPIRES, "wallclock_enforced": False},
        "phase_plan": plan([slot("current", options)]),
        "budget": {"revision": 1, "head_ref": ref("synthetic-ledger"), "remaining": capacity(),
                   "role_capacity": {"reviewer": 100, "worker": 100, "explorer": 100},
                   "phase_capacity": {"pre": 100, "post": 100, "repair": 100},
                   "parallel_available": True, "astra_active": 0, "astra_parallel_available": True,
                   "depth_allowed": True},
    }
    request = {
        "schema_version": "routing-request/1", "task_id": "consumer-task", "identity": fx.IDENTITY,
        "policy_digest": policy_digest(), "scenario": copy.deepcopy(fx.SCENARIO),
        "execution_mode": "PRODUCTION", "mode": "balanced", "slot_id": "current",
        "baseline_sha256": "b" * 64, "packet_sha256": "c" * 64,
        "message_sha256": "d" * 64, "evaluation_case_ref": "",
        "constraints": {"allowed_profiles": None, "deadline_ms": None, "strict_wallclock": False},
        "evidence": {"ready": True, "independence_required": True, "inline_sufficient": False,
                     "refs": [ref("synthetic-scope-evidence")]},
        "expected": snapshot_references(snapshot),
    }
    return request, snapshot


class PhasePlanTests(unittest.TestCase):
    def test_component_minima_cannot_fabricate_an_option(self):
        value = plan([slot("post", [option("g6-astra-low", 3), option("g6-sol-medium", 8)])])
        self.assertEqual("INFEASIBLE", feasible_witness(value, capacity(7, astra=0))["status"])

    def test_joint_witness_reserves_scarce_astra_capacity(self):
        options = [option("g6-astra-low", 2), option("g6-sol-medium", 5)]
        value = plan([slot("post", options), slot("repair", options, phase="repair")])
        result = feasible_witness(value, capacity(7, astra=1))
        self.assertEqual("FEASIBLE", result["status"])
        self.assertEqual(7, result["resources"]["units"])
        self.assertEqual(1, result["resources"]["astra_attempts"])

    def test_current_choice_must_preserve_later_slot_feasibility(self):
        value = plan([slot("pre", [option("g6-sol-high", 6)], phase="pre"),
                      slot("post", [option("g6-sol-medium", 6)])])
        self.assertEqual("INFEASIBLE", capacity_after_choice(
            value, "pre", "g6-sol-high", capacity(11))["status"])
        self.assertEqual("FEASIBLE", capacity_after_choice(
            value, "pre", "g6-sol-high", capacity(12))["status"])

    def test_role_limit_is_not_mistaken_for_global_future_capacity(self):
        value = plan([slot("work", [option("g56-luna-medium", 2)], role="worker", phase="pre"),
                      slot("post", [option("g6-sol-medium", 10)])])
        self.assertEqual("FEASIBLE", capacity_after_choice(
            value, "work", "g56-luna-medium", capacity(12),
            role_capacity={"worker": 2, "reviewer": 10, "explorer": 0})["status"])

    def test_future_same_role_capacity_is_also_protected(self):
        value = plan([slot("pre", [option("g6-sol-high", 6)], phase="pre"),
                      slot("post", [option("g6-sol-medium", 6)])])
        self.assertEqual("INFEASIBLE", capacity_after_choice(
            value, "pre", "g6-sol-high", capacity(100),
            role_capacity={"worker": 100, "reviewer": 10, "explorer": 100})["status"])

    def test_search_limit_is_unknown_not_false_infeasibility(self):
        value = plan([slot("a", [option("g6-sol-medium", 2)]),
                      slot("b", [option("g6-sol-medium", 2)])])
        self.assertEqual("SEARCH_LIMIT", feasible_witness(value, capacity(), max_states=1)["status"])

    def test_revision_cannot_drop_or_weaken_unfulfilled_scope(self):
        original = plan([slot("a", [option("g6-sol-medium", 2)]),
                         slot("b", [option("g6-sol-medium", 2)])])
        changed = copy.deepcopy(original)
        changed["revision"] = 2
        changed["slots"].pop()
        with self.assertRaisesRegex(RoutingError, "REMOVAL"):
            validate_revision(original, changed)
        changed = copy.deepcopy(original)
        changed["revision"] = 2
        changed["slots"][0]["scenario"]["risk"] = 0
        with self.assertRaisesRegex(RoutingError, "DOWNGRADE"):
            validate_revision(original, changed)

    def test_dependency_cycle_and_unproven_waiver_reject(self):
        value = plan([slot("a", [option("g6-sol-medium", 2)])])
        value["slots"][0]["depends_on"] = ["a"]
        with self.assertRaisesRegex(RoutingError, "CYCLE"):
            validate_plan(value)
        value["slots"][0]["depends_on"] = []
        value["slots"][0]["status"] = "WAIVED"
        with self.assertRaisesRegex(RoutingError, "WAIVER"):
            validate_plan(value)


class SelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = fx.experiment(1000, ("g6-sol-medium", "g6-sol-high", "g6-astra-low"),
                             origin="desktop-evaluation")
        for row in data["samples"]:
            number = int(row["case_id"].split("-")[1])
            row["clean"] = number >= 80 and number != 999
            if row["profile_id"] == "g6-sol-medium" and number < 80:
                row["passed"] = False
            if row["profile_id"] == "g6-sol-high" and number < 20:
                row["passed"] = False
            row["case_ref"] = fx.case_reference(row)
        fx.refreeze_protocol(data)
        costs = fx.costs(data)
        amounts = {"g6-sol-medium": (10, 100), "g6-sol-high": (16, 110), "g6-astra-low": (40, 115)}
        for cost in costs:
            cost["plan_cost"], cost["latency_ms"] = amounts[cost["profile_id"]]
            cost["reserve_units"] = cost["plan_cost"]
        cls.bundle = build_bundle(data, costs, bundle_id="synthetic-selector-bundle",
                                  created_at=fx.NOW, expires_at=fx.EXPIRES)

    def test_same_model_upgrade_and_cross_model_low_are_compared_by_gain(self):
        request, snapshot = prepared(self.bundle)
        self.assertEqual("g6-sol-high", select(request, snapshot)["approved_profile"])
        request["mode"] = "deep"
        self.assertEqual("g6-astra-low", select(request, snapshot)["approved_profile"])
        request["mode"] = "economy"
        self.assertEqual("g6-sol-medium", select(request, snapshot)["approved_profile"])

    def test_missing_evidence_never_selects_stronger_model(self):
        request, snapshot = prepared(self.bundle)
        request["evidence"]["ready"] = False
        self.assertEqual("NEEDS_EVIDENCE", select(request, snapshot)["status"])

    def test_pure_selection_never_mutates_budget_or_creates_a_permit(self):
        request, snapshot = prepared(self.bundle)
        before = copy.deepcopy(snapshot)
        result = select(request, snapshot)
        self.assertEqual(before, snapshot)
        self.assertEqual("CANDIDATE_SELECTED", result["status"])
        self.assertNotIn("permit_ref", result)

    def test_stale_revision_or_card_digest_fails_before_selection(self):
        request, snapshot = prepared(self.bundle)
        for key in ("ledger_revision", "capability_revision", "plan_revision", "cards_ref"):
            changed = copy.deepcopy(request)
            changed["expected"][key] = 9 if key.endswith("revision") else ref("foreign")
            self.assertEqual("STALE_SNAPSHOT", select(changed, snapshot)["status"])

    def test_permutation_does_not_change_winner(self):
        request, snapshot = prepared(self.bundle)
        for order in itertools.permutations(snapshot["cards"]["costs"]):
            changed = copy.deepcopy(snapshot)
            changed["cards"]["costs"] = list(order)
            current_request = copy.deepcopy(request)
            current_request["expected"] = snapshot_references(changed)
            self.assertEqual("g6-sol-high", select(current_request, changed)["approved_profile"])

    def test_unenforced_wallclock_limit_is_not_promised(self):
        request, snapshot = prepared(self.bundle)
        request["constraints"].update(strict_wallclock=True, deadline_ms=1000)
        self.assertEqual("DEADLINE_OR_SCOPE_UNSUPPORTED", select(request, snapshot)["status"])

    def test_small_budget_does_not_lower_quality(self):
        request, snapshot = prepared(self.bundle)
        snapshot["budget"]["remaining"]["units"] = 9
        request["expected"] = snapshot_references(snapshot)
        self.assertEqual("BUDGET_OR_PHASE_HOLD_BLOCKED", select(request, snapshot)["status"])

    def test_synthetic_card_set_cannot_be_promoted_by_mode_change(self):
        request, snapshot = prepared(self.bundle)
        snapshot["cards"]["origin"] = "evaluation"
        request["expected"] = snapshot_references(snapshot)
        self.assertEqual("CALIBRATION_REQUIRED", select(request, snapshot)["status"])


if __name__ == "__main__":
    unittest.main()
