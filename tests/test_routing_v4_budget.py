"""中文：V4 追加事务与恢复；隔离临时账本和合成宿主回执。

English: V4 transactions and recovery with isolated ledgers and synthetic receipts.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4 as budget
from cp_runtime.routing_contract import RoutingError, policy_digest, ref
from cp_runtime.routing_v4 import combine_cards, snapshot_references
from test_routing_v4_selection_phase import prepared, slot, capacity
import v4_fixtures as fx


class BudgetFixture:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.path = self.directory / "budget.jsonl"
        data = fx.experiment(origin="desktop-evaluation")
        self.request, self.snapshot = prepared(fx.bundle(data))
        self.request["mode"] = "economy"
        self.identity = {**fx.IDENTITY, "task_id": self.request["task_id"], "budget_id": "budget-v4"}
        self.binding = {
            "schema_version": "dispatch-root/2", "repo_path": str(self.repo),
            "profile_path": str(self.directory / "profile.json"), "profile_binding_sha256": "a" * 64,
            "envelope_identity_ref": ref("synthetic-envelope"), "host_session_ref": ref("synthetic-session"),
            "policy_id": "reviewer-matrix-v4", "policy_digest": policy_digest(),
        }
        self.sources = {
            "root_envelope": str(self.directory / "envelope.json"),
            "capability": str(self.directory / "capability.json"),
            "card_sets": [], "evaluation_costs": "", "evaluation_ref": "", "evidence_paths": {},
        }

    def init(self):
        return budget.initialize(
            self.path, declared_identity=self.identity, root_binding=self.binding, sources=self.sources,
            execution_mode=self.snapshot["execution_mode"], capacity=self.snapshot["budget"]["remaining"],
            role_capacity=self.snapshot["budget"]["role_capacity"],
            phase_capacity=self.snapshot["budget"]["phase_capacity"], phase_plan=self.snapshot["phase_plan"])

    def load(self, state, request, now):
        value = copy.deepcopy(self.snapshot)
        value["phase_plan"] = copy.deepcopy(state["phase_plan"])
        value["budget"] = budget.snapshot_budget(state)
        value["now"] = now
        return value

    def prepare(self, key="attempt-one", transition=None):
        return budget.prepare(self.path, self.request, dispatch_key=key, depth=1,
                              snapshot_loader=self.load, transition=transition)

    def reserve(self, decision, call="host-one", nonce=""):
        params = decision["request_parameters"]
        return budget.approve_and_reserve(
            self.path, permit_id=decision["permit_id"], host_dispatch_id=call,
            model=params["model"], effort=params["reasoning_effort"], agent_type=params["agent_type"],
            snapshot_loader=self.load, message_sha256=self.request["message_sha256"], nonce=nonce)

    def complete(self, decision, call="host-one", agent="agent-one"):
        attempt = self.reserve(decision, call)
        budget.record_receipt(self.path, host_dispatch_id=call, agent_id=agent)
        budget.record_observation(self.path, agent_id=agent, phase="stop", outcome="UNKNOWN")
        return attempt


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = BudgetFixture(self.temp.name)
        self.fixture.init()

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_does_not_charge_or_invalidate_its_own_budget_snapshot(self):
        before = budget.read_budget(self.fixture.path)
        selected = self.fixture.prepare()
        after = budget.read_budget(self.fixture.path)
        self.assertEqual(before["resource_revision"], after["resource_revision"])
        self.assertEqual(before["resource_ref"], after["resource_ref"])
        self.assertGreater(after["sequence"], before["sequence"])
        self.assertEqual(0, after["_usage_cache"]["resources"]["units"])
        self.assertEqual("RESERVED", self.fixture.reserve(selected)["state"])

    def test_nonce_plaintext_never_enters_ledger(self):
        selected = self.fixture.prepare()
        nonce = selected["native_message_prefix"].split()[1]
        self.assertNotIn(nonce, self.fixture.path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(RoutingError, "NONCE"):
            self.fixture.reserve(selected, nonce="0" * 64)
        self.fixture.reserve(selected, nonce=nonce)

    def test_same_host_retry_is_idempotent_but_different_host_cannot_reuse_permit(self):
        selected = self.fixture.prepare()
        first = self.fixture.reserve(selected)
        second = self.fixture.reserve(selected)
        self.assertEqual(first["reservation_id"], second["reservation_id"])
        self.assertTrue(second["idempotent"])
        with self.assertRaisesRegex(RoutingError, "PERMIT_ALREADY_CONSUMED"):
            self.fixture.reserve(selected, call="host-two")
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(1, len(state["reservations"]))
        self.assertEqual(selected["reserve_units"], state["_usage_cache"]["resources"]["units"])

    def test_concurrent_different_host_calls_reserve_only_once(self):
        selected = self.fixture.prepare()
        def run(call):
            try:
                return self.fixture.reserve(selected, call)["state"]
            except RoutingError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(run, ("host-a", "host-b")))
        self.assertEqual(["PERMIT_ALREADY_CONSUMED", "RESERVED"], sorted(result))
        self.assertEqual(1, len(budget.read_budget(self.fixture.path)["reservations"]))

    def test_started_or_created_attempt_cannot_be_dispatched_again(self):
        selected = self.fixture.prepare()
        self.fixture.reserve(selected)
        budget.record_receipt(self.fixture.path, host_dispatch_id="host-one", agent_id="agent-one")
        with self.assertRaisesRegex(RoutingError, "ALREADY_STARTED"):
            self.fixture.reserve(selected)

    def test_identity_link_cannot_assign_one_uuid_to_two_reserved_calls(self):
        revised = copy.deepcopy(budget.read_budget(self.fixture.path)["phase_plan"])
        second = copy.deepcopy(revised["slots"][0])
        second["slot_id"] = "second"
        revised["slots"].append(second)
        revised["revision"] += 1
        budget.revise_plan(self.fixture.path, revised, reason_ref=ref("second-review-scope"))
        attempt = self.fixture.reserve(self.fixture.prepare("first_task"))
        budget.record_receipt(self.fixture.path, host_dispatch_id="host-one", agent_id="/root/first_task")
        budget.record_observation(self.fixture.path, agent_id="unique-host-uuid", phase="stop")
        link = {"reservation_id": attempt["reservation_id"], "task_path": "/root/first_task",
                "agent_id": "unique-host-uuid", "dispatch_key": "first_task",
                "role": self.fixture.request["scenario"]["role"], "proof_ref": ref("verified-header")}
        with self.assertRaisesRegex(RoutingError, "TASK_MISMATCH"):
            budget.link_host_identity(self.fixture.path, **{**link, "task_path": "/root/foreign_task"})
        budget.link_host_identity(self.fixture.path, **link)
        budget.link_host_identity(self.fixture.path, **link)
        self.fixture.request["slot_id"] = "second"
        another = self.fixture.reserve(self.fixture.prepare("second_task"), "host-two")
        with self.assertRaisesRegex(RoutingError, "RECEIPT_COLLISION"):
            budget.record_receipt(self.fixture.path, host_dispatch_id="host-two", agent_id="unique-host-uuid")
        budget.record_receipt(self.fixture.path, host_dispatch_id="host-two", agent_id="/root/second_task")
        with self.assertRaisesRegex(RoutingError, "IDENTITY_LINK_CONFLICT"):
            budget.link_host_identity(self.fixture.path, **{**link, "reservation_id": another["reservation_id"],
                "task_path": "/root/second_task", "dispatch_key": "second_task"})
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(1, len(state["host_identity_links"]))
        self.assertEqual(1, state["_usage_cache"]["active"])
        self.assertEqual(2, state["_usage_cache"]["resources"]["attempts"])

    def test_stop_before_receipt_projects_completed_and_awaiting_result_atomically(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.reserve(selected)
        budget.record_observation(self.fixture.path, agent_id="agent-one", phase="stop", outcome="UNKNOWN")
        pending = budget.read_budget(self.fixture.path)
        self.assertEqual("RESERVED", pending["reservations"][attempt["reservation_id"]]["state"])
        self.assertEqual(1, pending["_usage_cache"]["active"])
        budget.record_receipt(self.fixture.path, host_dispatch_id="host-one", agent_id="agent-one")
        final = budget.read_budget(self.fixture.path)
        self.assertEqual("COMPLETED", final["reservations"][attempt["reservation_id"]]["state"])
        self.assertEqual("AWAITING_RESULT", final["phase_plan"]["slots"][0]["status"])
        self.assertEqual(0, final["_usage_cache"]["active"])
        budget.record_observation(self.fixture.path, agent_id="agent-one", phase="start")
        self.assertEqual("COMPLETED", budget.read_budget(self.fixture.path)["reservations"][attempt["reservation_id"]]["state"])

    def test_missing_receipt_or_cancellation_does_not_refund(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.reserve(selected)
        before = self.fixture.path.read_bytes()
        with self.assertRaisesRegex(RoutingError, "NOT_STARTED_PROOF"):
            budget.release_not_started(self.fixture.path, reservation_id=attempt["reservation_id"],
                                       proof_ref=ref("cancel-request"))
        self.assertEqual(before, self.fixture.path.read_bytes())

    def test_known_unsuccessful_stop_only_accepts_incomplete_without_refund(self):
        for outcome in ("CANCELLED", "FAILED", "PARTIAL", "BLOCKED"):
            for stop_first in (False, True):
                with self.subTest(outcome=outcome, stop_first=stop_first), tempfile.TemporaryDirectory() as directory:
                    fixture = BudgetFixture(directory)
                    fixture.init()
                    selected = fixture.prepare()
                    attempt = fixture.reserve(selected)
                    receipt = lambda: budget.record_receipt(
                        fixture.path, host_dispatch_id="host-one", agent_id="agent-one")
                    stop = lambda: budget.record_observation(
                        fixture.path, agent_id="agent-one", phase="stop", outcome=outcome)
                    first, second = (stop, receipt) if stop_first else (receipt, stop)
                    first(); second()
                    before = fixture.path.read_bytes()
                    fields = {"reservation_id": attempt["reservation_id"], "result_ref": ref("result"),
                              "response_ref": ref("response"),
                              "baseline_sha256": fixture.request["baseline_sha256"]}
                    for status in ("pass", "nonblocking", "blocking"):
                        with self.assertRaisesRegex(RoutingError, "CONFLICTS_WITH_HOST_OUTCOME"):
                            budget.accept_result(fixture.path, status=status, **fields)
                        self.assertEqual(before, fixture.path.read_bytes())
                    state = budget.accept_result(fixture.path, status="incomplete", **fields)
                    self.assertEqual("PENDING", state["phase_plan"]["slots"][0]["status"])
                    self.assertEqual(selected["reserve_units"], state["_usage_cache"]["resources"]["units"])
                    self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])
                    self.assertEqual(outcome, state["reservations"][attempt["reservation_id"]]["outcome"])

    def test_unknown_host_outcome_needs_a_separate_result_and_is_not_rewritten(self):
        attempt = self.fixture.complete(self.fixture.prepare())
        state = budget.read_budget(self.fixture.path)
        self.assertFalse(state["accepted_results"])
        self.assertEqual("AWAITING_RESULT", state["phase_plan"]["slots"][0]["status"])
        state = budget.accept_result(
            self.fixture.path, reservation_id=attempt["reservation_id"], result_ref=ref("review-result"),
            status="pass", response_ref=ref("validated-response"),
            baseline_sha256=self.fixture.request["baseline_sha256"])
        self.assertEqual("UNKNOWN", state["reservations"][attempt["reservation_id"]]["outcome"])
        self.assertEqual("SATISFIED", state["phase_plan"]["slots"][0]["status"])

    def test_reserved_repair_and_new_evidence_retry_resolve_blockers_in_same_root(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = BudgetFixture(directory)
            post = fx.experiment(origin="desktop-evaluation")
            repair = fx.experiment(origin="desktop-evaluation")
            repair["scenario"]["phase"] = "repair"
            fx.refreeze_protocol(repair)
            repair_bundle = fx.bundle(repair)
            _, repair_snapshot = prepared(repair_bundle)
            repair_slot = copy.deepcopy(repair_snapshot["phase_plan"]["slots"][0])
            repair_slot.update(slot_id="repair", scenario=repair["scenario"],
                               condition="repair-after-post", depends_on=["current"])
            fixture.snapshot["phase_plan"]["slots"].append(repair_slot)
            fixture.snapshot["cards"] = combine_cards(
                [fx.bundle(post), repair_bundle], [ref("post-publication"), ref("repair-publication")],
                declared_identity=fx.IDENTITY)
            fixture.init()
            initial = fixture.complete(fixture.prepare())
            blocker = ref("post-blocker")
            budget.accept_result(
                fixture.path, reservation_id=initial["reservation_id"], result_ref=blocker,
                status="blocking", response_ref=ref("post-response"),
                baseline_sha256=fixture.request["baseline_sha256"])
            state = budget.read_budget(fixture.path)
            self.assertEqual(["SATISFIED", "PENDING"], [item["status"] for item in state["phase_plan"]["slots"]])
            with self.assertRaisesRegex(RoutingError, "WAIVER"):
                budget.waive_repair(fixture.path, slot_id="repair", post_result_ref=blocker,
                                    evidence_ref=ref("unproven-waiver"))
            fixture.request.update(slot_id="repair", scenario=repair["scenario"],
                                   baseline_sha256="e" * 64, packet_sha256="f" * 64)
            fixture.request["evidence"]["refs"].append(ref("first-fix-evidence"))
            first_repair = fixture.complete(fixture.prepare("repair-one"), "repair-call", "repair-agent")
            unresolved = ref("repair-blocker")
            budget.accept_result(
                fixture.path, reservation_id=first_repair["reservation_id"], result_ref=unresolved,
                status="blocking", response_ref=ref("repair-response"),
                baseline_sha256=fixture.request["baseline_sha256"])
            transition = {"prior_reservation_id": first_repair["reservation_id"],
                          "prior_result_ref": unresolved, "reason": "TARGETED_REPAIR"}
            before = fixture.path.read_bytes()
            with self.assertRaisesRegex(RoutingError, "REQUIRES_NEW_EVIDENCE"):
                fixture.prepare("repair-two", transition)
            self.assertEqual(before, fixture.path.read_bytes())
            fixture.request["evidence"]["refs"].append(ref("second-fix-evidence"))
            final = fixture.complete(fixture.prepare("repair-two", transition), "final-call", "final-agent")
            budget.accept_result(
                fixture.path, reservation_id=final["reservation_id"], result_ref=ref("repair-pass"),
                status="pass", response_ref=ref("final-response"),
                baseline_sha256=fixture.request["baseline_sha256"], supersedes=[blocker, unresolved])
            state = budget.close(fixture.path, outcome="PASS", evidence_ref=ref("close"))
            self.assertEqual("PASS", state["outcome"])
            self.assertEqual(3, state["_usage_cache"]["resources"]["attempts"])
            self.assertEqual(30, state["_usage_cache"]["resources"]["units"])

    def test_not_started_proof_releases_units_but_never_attempt_counts(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.reserve(selected)
        proof = ref("synthetic-trusted-not-created")
        budget.record_receipt(self.fixture.path, host_dispatch_id="host-one",
                              disposition="not-started", not_started_proof=proof)
        budget.release_not_started(self.fixture.path, reservation_id=attempt["reservation_id"], proof_ref=proof)
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(0, state["_usage_cache"]["resources"]["units"])
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])
        self.assertEqual("PENDING", state["phase_plan"]["slots"][0]["status"])
        with self.assertRaisesRegex(RoutingError, "RELEASED_ATTEMPT_REUSE"):
            self.fixture.reserve(selected)

    def test_incomplete_result_retry_needs_actual_new_evidence(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.complete(selected)
        result_ref = ref("incomplete-result")
        budget.accept_result(self.fixture.path, reservation_id=attempt["reservation_id"],
                             result_ref=result_ref, status="incomplete", response_ref=ref("response"),
                             baseline_sha256=self.fixture.request["baseline_sha256"])
        transition = {"prior_reservation_id": attempt["reservation_id"],
                      "prior_result_ref": result_ref, "reason": "NEW_EVIDENCE"}
        before = self.fixture.path.read_bytes()
        with self.assertRaisesRegex(RoutingError, "REQUIRES_NEW_EVIDENCE"):
            self.fixture.prepare("attempt-two", transition)
        self.assertEqual(before, self.fixture.path.read_bytes())
        self.fixture.request["evidence"]["refs"].append(ref("new-parent-evidence"))
        self.assertEqual("CANDIDATE_SELECTED", self.fixture.prepare("attempt-two", transition)["status"])

    def test_blocking_result_cannot_close_as_pass_even_when_slot_finished(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.complete(selected)
        budget.accept_result(self.fixture.path, reservation_id=attempt["reservation_id"],
                             result_ref=ref("blocking"), status="blocking", response_ref=ref("response"),
                             baseline_sha256=self.fixture.request["baseline_sha256"])
        with self.assertRaisesRegex(RoutingError, "UNRESOLVED"):
            budget.close(self.fixture.path, outcome="PASS", evidence_ref=ref("close"))

    def test_result_is_idempotent_and_conflicting_replacement_rejects(self):
        selected = self.fixture.prepare()
        attempt = self.fixture.complete(selected)
        fields = {"reservation_id": attempt["reservation_id"], "result_ref": ref("pass-result"),
                  "status": "pass", "response_ref": ref("response"),
                  "baseline_sha256": self.fixture.request["baseline_sha256"]}
        budget.accept_result(self.fixture.path, **fields)
        before = self.fixture.path.read_bytes()
        budget.accept_result(self.fixture.path, **fields)
        self.assertEqual(before, self.fixture.path.read_bytes())
        with self.assertRaisesRegex(RoutingError, "RESULT_CONFLICT"):
            budget.accept_result(self.fixture.path, **{**fields, "status": "blocking"})

    def test_revoked_capability_snapshot_rejects_even_same_host_retry(self):
        selected = self.fixture.prepare()
        self.fixture.reserve(selected)
        self.fixture.snapshot["capability"]["revision"] += 1
        with self.assertRaisesRegex(RoutingError, "STALE"):
            self.fixture.reserve(selected)

    def test_tampered_early_event_and_partial_tail_fail_closed(self):
        selected = self.fixture.prepare()
        original = self.fixture.path.read_bytes()
        rows = original.decode().splitlines()
        row = json.loads(rows[0])
        row["data"]["capacity"]["units"] += 1
        rows[0] = json.dumps(row)
        self.fixture.path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RoutingError, "HASH"):
            budget.read_budget(self.fixture.path)
        self.fixture.path.write_bytes(original[:-1])
        with self.assertRaisesRegex(RoutingError, "PARTIAL_TAIL"):
            budget.read_budget(self.fixture.path)

    def test_crash_before_atomic_commit_does_not_leave_consumed_half_state(self):
        selected = self.fixture.prepare()
        before = self.fixture.path.read_bytes()
        with patch("cp_runtime.budget_v4.atomic_write_bytes", side_effect=OSError("synthetic-write-failure")):
            with self.assertRaises(OSError):
                self.fixture.reserve(selected)
        self.assertEqual(before, self.fixture.path.read_bytes())
        self.assertEqual("RESERVED", self.fixture.reserve(selected)["state"])

    def test_same_root_initialization_cannot_reset_used_capacity(self):
        selected = self.fixture.prepare()
        self.fixture.reserve(selected)
        state = self.fixture.init()
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])
        self.fixture.snapshot["budget"]["remaining"]["units"] += 1
        with self.assertRaisesRegex(RoutingError, "INITIALIZATION_CONFLICT"):
            self.fixture.init()


class AstraConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = BudgetFixture(self.temp.name)
        data = fx.experiment(profiles=("g6-sol-medium", "g6-astra-low"), origin="desktop-evaluation")
        self.fixture.request, self.fixture.snapshot = prepared(fx.bundle(data))
        self.fixture.request["mode"] = "economy"
        original = self.fixture.snapshot["phase_plan"]["slots"][0]
        for name in ("second", "ordinary"):
            added = copy.deepcopy(original)
            added["slot_id"] = name
            self.fixture.snapshot["phase_plan"]["slots"].append(added)
        self.fixture.init()
        self.fixture.request["constraints"]["allowed_profiles"] = ["g6-astra-low"]

    def tearDown(self):
        self.temp.cleanup()

    def first(self):
        selected = self.fixture.prepare("astra_one")
        return selected, self.fixture.reserve(selected, "astra-call-one")

    def test_second_astra_is_blocked_but_ordinary_parallelism_remains_available(self):
        self.first()
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(1, state["_usage_cache"]["astra_active"])
        self.fixture.request["slot_id"] = "second"
        before = self.fixture.path.read_bytes()
        self.assertEqual("ASTRA_PARALLEL_LIMIT", self.fixture.prepare("astra_two")["status"])
        self.assertEqual(before, self.fixture.path.read_bytes())
        self.fixture.request.update(slot_id="ordinary")
        self.fixture.request["constraints"]["allowed_profiles"] = ["g6-sol-medium"]
        self.fixture.reserve(self.fixture.prepare("ordinary_one"), "ordinary-call-one")
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(2, state["_usage_cache"]["active"])
        self.assertEqual(1, state["_usage_cache"]["astra_active"])

    def test_atomic_reservation_rejects_a_loader_that_hides_active_astra(self):
        self.first()
        self.fixture.request["slot_id"] = "second"
        actual_loader = self.fixture.load
        def misleading(state, request, now):
            snapshot = actual_loader(state, request, now)
            snapshot["budget"].update(astra_active=0, astra_parallel_available=True)
            return snapshot
        self.fixture.load = misleading
        selected = self.fixture.prepare("astra_two")
        before = self.fixture.path.read_bytes()
        with self.assertRaisesRegex(RoutingError, "ASTRA_PARALLEL_LIMIT"):
            self.fixture.reserve(selected, "astra-call-two")
        self.assertEqual(before, self.fixture.path.read_bytes())

    def test_all_trusted_stop_outcomes_release_inflight_capacity_without_refunding_attempts(self):
        for outcome in ("PASS", "CANCELLED", "FAILED", "PARTIAL", "BLOCKED", "UNKNOWN"):
            for stop_first in (False, True):
                with self.subTest(outcome=outcome, stop_first=stop_first), tempfile.TemporaryDirectory() as directory:
                    fixture = BudgetFixture(directory)
                    fixture.request = copy.deepcopy(self.fixture.request)
                    fixture.snapshot = copy.deepcopy(self.fixture.snapshot)
                    fixture.init()
                    selected = fixture.prepare("astra_one")
                    attempt = fixture.reserve(selected, "astra-call-one")
                    stop = lambda: budget.record_observation(fixture.path, agent_id="host-astra", phase="stop", outcome=outcome)
                    receipt = lambda: budget.record_receipt(fixture.path, host_dispatch_id="astra-call-one", agent_id="host-astra")
                    if stop_first:
                        stop()
                        self.assertEqual(1, budget.read_budget(fixture.path)["_usage_cache"]["astra_active"])
                        receipt()
                    else:
                        receipt()
                        budget.record_observation(fixture.path, agent_id="host-astra", phase="start")
                        stop()
                    state = budget.read_budget(fixture.path)
                    self.assertEqual(0, state["_usage_cache"]["astra_active"])
                    self.assertEqual(outcome, state["reservations"][attempt["reservation_id"]]["outcome"])
                    self.assertEqual(selected["reserve_units"], state["_usage_cache"]["resources"]["units"])
                    self.assertEqual(1, state["_usage_cache"]["resources"]["astra_attempts"])
                    fixture.request["slot_id"] = "second"
                    fixture.reserve(fixture.prepare("astra_two"), "astra-call-two")
                    final = budget.read_budget(fixture.path)
                    self.assertEqual(1, final["_usage_cache"]["astra_active"])
                    self.assertEqual(2, final["_usage_cache"]["resources"]["astra_attempts"])

    def test_identity_link_and_not_started_proof_preserve_cumulative_astra_attempts(self):
        _, attempt = self.first()
        budget.record_observation(self.fixture.path, agent_id="host-uuid", phase="stop")
        budget.link_host_identity(self.fixture.path, reservation_id=attempt["reservation_id"],
            task_path="/root/astra_one", agent_id="host-uuid", dispatch_key="astra_one",
            role=self.fixture.request["scenario"]["role"], proof_ref=ref("verified-header"))
        self.assertEqual(1, budget.read_budget(self.fixture.path)["_usage_cache"]["astra_active"])
        budget.record_receipt(self.fixture.path, host_dispatch_id="astra-call-one", agent_id="/root/astra_one")
        self.assertEqual(0, budget.read_budget(self.fixture.path)["_usage_cache"]["astra_active"])
        self.fixture.request["slot_id"] = "second"
        selected = self.fixture.prepare("astra_two")
        another = self.fixture.reserve(selected, "astra-call-two")
        proof = ref("trusted-not-started")
        budget.record_receipt(self.fixture.path, host_dispatch_id="astra-call-two",
                              disposition="not-started", not_started_proof=proof)
        budget.release_not_started(self.fixture.path, reservation_id=another["reservation_id"], proof_ref=proof)
        state = budget.read_budget(self.fixture.path)
        self.assertEqual(0, state["_usage_cache"]["astra_active"])
        self.assertEqual(2, state["_usage_cache"]["resources"]["attempts"])
        self.assertEqual(2, state["_usage_cache"]["resources"]["astra_attempts"])


if __name__ == "__main__":
    unittest.main()
