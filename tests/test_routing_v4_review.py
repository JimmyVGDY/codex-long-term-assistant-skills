"""中文：V9/V6 归属与投影恢复；无真实模型调用。

English: V9/V6 ownership and projection recovery without model calls.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4, review_v4
from cp_runtime.common import atomic_write_json
from cp_runtime.routing_contract import RoutingError, ref
import test_routing_v4_context as context_fixtures


class ReviewV4Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = context_fixtures.ContextTests(methodName="runTest")
        self.fixture.setUp()
        self.directory = self.fixture.root / "review"
        self.state = review_v4.initialize(self.directory, ledger_path=self.fixture.path,
                                          boundary_id="v4-boundary")
        self.prepared = review_v4.prepare(self.directory, self.fixture.request,
                                          dispatch_key="review_one", depth=1,
                                          snapshot_loader=self.fixture.loader)

    def tearDown(self):
        self.fixture.tearDown()

    def completed_result(self):
        params = self.prepared["request_parameters"]
        reservation = budget_v4.approve_and_reserve(
            self.fixture.path, permit_id=self.prepared["permit_id"], host_dispatch_id="review-call",
            model=params["model"], effort=params["reasoning_effort"], agent_type=params["agent_type"],
            message_sha256=self.fixture.request["message_sha256"], snapshot_loader=self.fixture.loader)
        budget_v4.record_receipt(self.fixture.path, host_dispatch_id="review-call", agent_id="review-agent")
        budget_v4.record_observation(self.fixture.path, agent_id="review-agent", phase="stop")
        result = review_v4.result_template(self.directory, self.prepared["permit_id"])
        result.update(status="pass", summary="Synthetic no-findings result", checked_scope=["README.md"])
        path = self.fixture.root / "result.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        return reservation, result, path

    def test_result_binds_one_review_owner_and_exact_permit(self):
        reservation, payload, path = self.completed_result()
        state = review_v4.record_result(self.directory, path, response_ref=ref("synthetic-response"))
        self.assertEqual(9, state["schema_version"])
        self.assertEqual(6, payload["schema_version"])
        self.assertTrue(state["entries"][self.prepared["permit_id"]]["result_ref"])
        self.assertEqual(1, len(budget_v4.read_budget(self.fixture.path)["accepted_results"]))
        self.assertEqual("PASS", review_v4.close(self.directory, conclusion="PASS")["conclusion"])
        self.assertEqual("PASS", review_v4.close(self.directory, conclusion="PASS")["conclusion"])
        with self.assertRaisesRegex(RoutingError, "CLOSE_CONFLICT"):
            review_v4.close(self.directory, conclusion="FAILED")

    def test_prepared_permit_prevents_closing_before_host_decision(self):
        with self.assertRaisesRegex(RoutingError, "ACTIVE_ATTEMPTS"):
            review_v4.close(self.directory, conclusion="CANCELLED")
        budget_v4.revoke_prepare(self.fixture.path, permit_id=self.prepared["permit_id"],
                                  reason_ref=ref("synthetic-revocation"))
        self.assertEqual("CANCELLED", review_v4.close(self.directory, conclusion="CANCELLED")["conclusion"])
        with self.assertRaisesRegex(RoutingError, "NOT_OPEN"):
            review_v4.prepare(self.directory, self.fixture.request, dispatch_key="after-close", depth=1,
                              snapshot_loader=self.fixture.loader)

    def test_missing_immutable_result_blocks_pass_close(self):
        _, _, path = self.completed_result()
        state = review_v4.record_result(self.directory, path, response_ref=ref("synthetic-response"))
        stored = Path(next(iter(state["results"].values()))["result_path"])
        stored.unlink()
        with self.assertRaises(FileNotFoundError):
            review_v4.close(self.directory, conclusion="PASS")

    def test_pass_without_checked_scope_or_after_baseline_change_is_rejected(self):
        _, payload, path = self.completed_result()
        with self.assertRaisesRegex(RoutingError, "COMPLETED_SCOPE_REQUIRED"):
            review_v4.validate_result({**payload, "checked_scope": []}, payload)
        review_v4.record_result(self.directory, path, response_ref=ref("synthetic-response"))
        (self.fixture.repo / "README.md").write_text("Changed after review", encoding="utf-8")
        with self.assertRaisesRegex(RoutingError, "CLOSE_BASELINE_STALE"):
            review_v4.close(self.directory, conclusion="PASS")

    def test_stale_result_can_record_incomplete_without_claiming_current_pass(self):
        reservation, payload, path = self.completed_result()
        (self.fixture.repo / "README.md").write_text("Changed during review", encoding="utf-8")
        payload.update(status="incomplete", unverified_items=["Current baseline changed"])
        path.write_text(json.dumps(payload), encoding="utf-8")
        review_v4.record_result(self.directory, path, response_ref=ref("synthetic-response"))
        result = budget_v4.read_budget(self.fixture.path)["accepted_results"][reservation["reservation_id"]]
        self.assertEqual("incomplete", result["status"])
        with self.assertRaisesRegex(RoutingError, "UNRESOLVED_FINDINGS"):
            review_v4.close(self.directory, conclusion="PASS")

    def test_a_second_review_state_cannot_claim_same_slot(self):
        another = self.fixture.root / "another-review"
        review_v4.initialize(another, ledger_path=self.fixture.path, boundary_id="different-boundary")
        with self.assertRaisesRegex(RoutingError, "OWNER_CONFLICT"):
            review_v4.prepare(another, self.fixture.request, dispatch_key="review_two", depth=1,
                              snapshot_loader=self.fixture.loader)
        self.assertEqual(1, len(budget_v4.read_budget(self.fixture.path)["permits"]))

    def test_mutated_assignment_or_isolation_cannot_be_accepted(self):
        _, payload, _ = self.completed_result()
        for key, value in (("isolation_level", "system-readonly"), ("profile_id", "g6-astra-high"),
                           ("reserved_units", 0), ("decision_ref", ref("foreign"))):
            changed = {**payload, key: value}
            with self.assertRaisesRegex(RoutingError, "ASSIGNMENT"):
                review_v4.validate_result(changed, payload)

    def test_projection_interruption_recovers_committed_result_from_content_store(self):
        reservation, payload, path = self.completed_result()
        calls = 0
        original = review_v4.atomic_write_json
        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic projection interruption")
            return original(*args, **kwargs)
        with patch("cp_runtime.review_v4.atomic_write_json", side_effect=interrupted):
            with self.assertRaises(OSError):
                review_v4.record_result(self.directory, path, response_ref=ref("synthetic-response"))
        ledger = budget_v4.read_budget(self.fixture.path)
        self.assertIn(reservation["reservation_id"], ledger["accepted_results"])
        recovered = review_v4.reconcile(self.directory)
        self.assertEqual(1, len(recovered["results"]))
        self.assertEqual(1, len(ledger["reservations"]))

    def test_projection_cannot_inject_foreign_permit_ownership(self):
        other = self.fixture.root / "other-view"
        value = review_v4.initialize(other, ledger_path=self.fixture.path, boundary_id="other-boundary")
        value["entries"][self.prepared["permit_id"]] = {"state": "PREPARED"}
        atomic_write_json(other / review_v4.STATE_FILE, value, seal=True)
        with self.assertRaisesRegex(RoutingError, "PERMIT_UNKNOWN"):
            review_v4.result_template(other, self.prepared["permit_id"])


if __name__ == "__main__":
    unittest.main()
