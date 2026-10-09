"""中文：验证原子预占、未来预留与已创建尝试的不可变记账。

English: Atomic reserve, future holds, and immutable created-attempt accounting.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from cp_runtime import g6_budget_v1 as budget
from cp_runtime.g6_flexible_policy import PROFILES
from cp_runtime.routing_contract import RoutingError, ref


def facts(item="item-a"):
    return {"schema_version": "g6-task-facts/1",
            "identity": {"project_id": "project-a", "repo_fingerprint": ref("repo-a")},
            "task_id": "task-a", "work_item_id": item,
            "baseline_sha256": "a" * 64, "scope_ref": ref("scope-a"),
            "task_kind": "unknown", "task_kind_source": "unknown",
            "source_refs": [], "missing_evidence": ["quality_card"]}


def capability():
    return {"schema_version": "g6-desktop-capability/1",
            "available_profiles": list(PROFILES), "source_ref": ref("desktop-capability")}


class G6BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "budget.jsonl"
        self.repo = Path(__file__).resolve().parents[1]
        self.session = "session-a"

    def init(self, capacity="STANDARD", slots=None):
        return budget.initialize(self.path, identity_value=facts()["identity"],
                                 host_session_id=self.session, repo_path=self.repo,
                                 task_id="task-a",
                                 authorization_ref=ref("authorized-task"),
                                 capacity_class=capacity, required_slots=slots)

    def prepare(self, item="item-a", name="agent_a", **extra):
        return budget.prepare(self.path, facts=facts(item), capability=capability(), gates=[],
                              agent_type="worker", task_name=name, message="Do bounded work.",
                              decision_time="2026-10-09T08:00:00Z", **extra)

    def reserve(self, prepared, call="call-a"):
        return budget.approve_and_reserve(
            self.path, permit_id=prepared["permit_id"], host_call_id=call,
            session_id=self.session, cwd=self.repo,
            args=prepared["decision"]["exact_tool_parameters"], now="2026-10-09T08:01:00Z")

    def test_created_completion_charged_once_and_replayed(self):
        self.init()
        prepared = self.prepare()
        self.reserve(prepared)
        self.assertTrue(self.reserve(prepared)["idempotent"])
        budget.record_receipt(self.path, host_call_id="call-a", disposition="created",
                              agent_path="/root/agent_a", proof_ref=ref("native-created"))
        budget.record_terminal(self.path, agent_path="/root/agent_a", outcome="PASS",
                               proof_ref=ref("native-stop"))
        state = budget.read_budget(self.path)
        result = budget.snapshot(state, work_item_id="item-b", depth=0)
        self.assertEqual(result["completed_charged_units"], 4)
        self.assertEqual(result["completed_charged_attempts"], 1)
        self.assertEqual(result["inflight_reserved_units"], 0)

    def test_two_prepared_calls_cannot_double_spend(self):
        self.init(capacity="LIGHT")
        first = self.prepare(item="item-a", name="agent_a")
        second = self.prepare(item="item-b", name="agent_b")
        self.reserve(first)
        with self.assertRaises(RoutingError):
            self.reserve(second, call="call-b")
        state = budget.read_budget(self.path)
        self.assertEqual(len(state["reservations"]), 1)
        self.assertEqual(budget.snapshot(state, work_item_id="item-c", depth=0)
                         ["inflight_reserved_attempts"], 1)

    def test_required_future_slot_uses_its_allowed_profile_cost(self):
        slot = {"work_item_id": "later", "allowed_profiles": ["g6-astra-medium"],
                "baseline_profile": "g6-astra-medium"}
        self.init(slots=[slot])
        state = budget.read_budget(self.path)
        view = budget.snapshot(state, work_item_id="item-a", depth=0)
        self.assertEqual(view["future_required_hold_units"], 8)
        prepared = self.prepare(explicit_user_profile="g6-astra-high")
        self.assertIsNone(prepared["permit_id"])
        self.assertEqual(prepared["decision"]["decision"], "CONTINUE_LOCAL")

    def test_not_started_proof_releases_units_but_not_attempt(self):
        self.init()
        prepared = self.prepare()
        self.reserve(prepared)
        budget.record_receipt(self.path, host_call_id="call-a", disposition="not_started",
                              agent_path=None, proof_ref=ref("native-no-start"))
        result = budget.snapshot(budget.read_budget(self.path), work_item_id="item-b", depth=0)
        self.assertEqual(result["completed_charged_units"], 0)
        self.assertEqual(result["completed_charged_attempts"], 1)
        self.assertEqual(result["active_calls"], 0)

    def test_not_started_work_can_retry_without_resetting_attempts(self):
        self.init()
        first = self.prepare()
        self.reserve(first)
        budget.record_receipt(self.path, host_call_id="call-a", disposition="not_started",
                              agent_path=None, proof_ref=ref("native-no-start"))
        second = self.prepare(name="agent_b")
        self.reserve(second, call="call-b")
        view = budget.snapshot(budget.read_budget(self.path), work_item_id="other", depth=0)
        self.assertEqual(view["completed_charged_attempts"], 1)
        self.assertEqual(view["inflight_reserved_attempts"], 1)
        self.assertEqual(view["inflight_reserved_units"], 4)

    def test_required_slot_transfers_own_hold_without_double_charge(self):
        slot = {"work_item_id": "later", "allowed_profiles": ["g6-sol-medium"],
                "baseline_profile": "g6-sol-medium"}
        self.init(capacity="LIGHT", slots=[slot])
        before = budget.snapshot(budget.read_budget(self.path), work_item_id="other", depth=0)
        self.assertEqual(before["future_required_hold_units"], 4)
        prepared = self.prepare(item="later")
        self.assertEqual(prepared["decision"]["approved_profile"], "g6-sol-medium")
        self.reserve(prepared)
        after = budget.snapshot(budget.read_budget(self.path), work_item_id="other", depth=0)
        self.assertEqual(after["future_required_hold_units"], 0)
        self.assertEqual(after["inflight_reserved_units"], 4)

    def test_required_slot_cannot_be_satisfied_by_an_unapproved_cheaper_profile(self):
        slot = {"work_item_id": "later", "allowed_profiles": ["g6-astra-medium"],
                "baseline_profile": "g6-astra-medium"}
        self.init(slots=[slot])
        rejected = self.prepare(item="later", name="cheap", explicit_user_profile="g6-luna-low")
        self.assertIsNone(rejected["permit_id"])
        permitted = self.prepare(item="later", name="qualified")
        self.assertEqual(permitted["decision"]["approved_profile"], "g6-astra-medium")
        self.reserve(permitted)

    def test_exact_tool_parameters_and_root_identity_are_enforced(self):
        self.init()
        prepared = self.prepare()
        wrong = copy.deepcopy(prepared["decision"]["exact_tool_parameters"])
        wrong["reasoning_effort"] = "high"
        with self.assertRaises(RoutingError):
            budget.approve_and_reserve(self.path, permit_id=prepared["permit_id"],
                                       host_call_id="call-a", session_id=self.session,
                                       cwd=self.repo, args=wrong, now="2026-10-09T08:01:00Z")
        with self.assertRaises(RoutingError):
            budget.approve_and_reserve(self.path, permit_id=prepared["permit_id"],
                                       host_call_id="call-a", session_id="foreign-session",
                                       cwd=self.repo,
                                       args=prepared["decision"]["exact_tool_parameters"],
                                       now="2026-10-09T08:01:00Z")
        self.assertEqual(len(budget.read_budget(self.path)["reservations"]), 0)

    def test_journal_corruption_does_not_start_fresh_chain(self):
        self.init()
        with self.path.open("ab") as stream:
            stream.write(b'{"bad":true}\n')
        with self.assertRaises(RoutingError):
            budget.read_budget(self.path)

    def test_invalid_receipt_does_not_poison_the_existing_journal(self):
        self.init()
        self.reserve(self.prepare())
        before = self.path.read_bytes()
        with self.assertRaises(RoutingError):
            budget.record_receipt(self.path, host_call_id="call-a", disposition="created",
                                  agent_path=None, proof_ref=ref("invalid-created-receipt"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(budget.read_budget(self.path)["reservations"]), 1)

    def finish_adjusted(self, item, name, call):
        adjusted = self.prepare(item=item, name=name, adjustment={
            "requested_profile": "g6-sol-high", "source": "model_semantic", "reason": "",
            "source_ref": None})
        self.assertEqual(adjusted["decision"]["approved_profile"], "g6-sol-high")
        self.reserve(adjusted, call=call)
        budget.record_receipt(self.path, host_call_id=call, disposition="created",
                              agent_path="/root/"+name, proof_ref=ref(call))
        budget.record_terminal(self.path, agent_path="/root/"+name, outcome="FAILED", proof_ref=ref(name))

    def test_renamed_unknown_work_keeps_adjustment_limit_but_default_continues(self):
        self.init(capacity="STRICT")
        self.finish_adjusted("wording-one", "first", "first-call")
        self.finish_adjusted("wording-two", "second", "second-call")
        third = self.prepare(item="wording-three", name="third", adjustment={
            "requested_profile": "g6-sol-high", "source": "model_semantic", "reason": "",
            "source_ref": None})
        self.assertEqual(third["decision"]["approved_profile"], "g6-sol-medium")
        self.assertIsNotNone(third["permit_id"])

    def test_registered_split_shares_origin_without_charging_unrelated_work(self):
        slots = [{"work_item_id": item, "allowed_profiles": ["g6-sol-medium", "g6-sol-high"],
                  "baseline_profile": "g6-sol-medium", "origin_work_item_id": origin}
                 for item, origin in (("split-a", "original"), ("split-b", "original"),
                                      ("independent", "separate"))]
        self.init(capacity="STRICT", slots=slots)
        self.finish_adjusted("split-a", "split_first", "split-first-call")
        state = budget.read_budget(self.path)
        self.assertEqual(budget.snapshot(state, work_item_id="split-b", depth=0)["upward_adjustments_used"], 1)
        self.assertEqual(budget.snapshot(state, work_item_id="independent", depth=0)["upward_adjustments_used"], 0)


if __name__ == "__main__":
    unittest.main()
