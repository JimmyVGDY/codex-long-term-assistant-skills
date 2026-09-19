"""中文：V3 评分派发、预算并发与 V2 续写回归；使用合成任务身份。

English: V3 scored dispatch, concurrent accounting, and frozen V2 writer regressions.
"""
from __future__ import annotations

import copy
import json
import itertools
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import delegation_budget as budget  # noqa: E402
from cp_runtime.dispatch_policy import CURRENT_POLICY_ID, LEGACY_POLICY_ID, policy_digest, score_review  # noqa: E402
from test_dispatch_policy import CONTEXT, ROLE, evidence, sha  # noqa: E402


class MatrixDelegationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = self.root / "budget.jsonl"
        self.binding = {
            "schema_version": "dispatch-root/1", "repo_path": str(self.root),
            "profile_path": str(self.root / "synthetic-profile.json"),
            "profile_binding_sha256": "d" * 64,
            "envelope_identity_ref": sha("synthetic-envelope"),
            "host_session_ref": sha("synthetic-host-session"),
            "reviewer_policy_id": CURRENT_POLICY_ID, "reviewer_policy_digest": policy_digest(),
        }

    def tearDown(self):
        self.temp.cleanup()

    def init(self, budget_class="STRICT", extension=True, policy_id=CURRENT_POLICY_ID):
        return budget.initialize_budget(
            self.ledger, budget_id="SYNTHETIC-BUDGET", task_id=CONTEXT["task_id"],
            project_id=CONTEXT["project_id"], repo_fingerprint=CONTEXT["repo_fingerprint"],
            budget_class=budget_class, default_dispatch_profile="luna-low", policy_id=policy_id,
            review_extension=extension if policy_id == CURRENT_POLICY_ID else False,
            root_binding=self.binding if policy_id == CURRENT_POLICY_ID else None,
        )

    def decision(self, key, profile="sol-low", **overrides):
        native_nonce = overrides.pop("native_dispatch_nonce", "")
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"),
                                 ("impact", "critical_irreversible"), ("conflict", "confirmed"))
        selection = score_review(agent_type=ROLE, context=CONTEXT, reviewer_budget="deep",
                                 evidence_items=atoms, proofs=proofs, requirements=[profile])
        assignment = {"reviewer": key, "agent_type": ROLE, "boundary_id": "synthetic-boundary",
                      "phase": "post", "round": 1, "packet_sha256": CONTEXT["packet_sha256"],
                      "acceptable_profiles": [profile]}
        args = {"dispatch_key": key, "decision": "DELEGATE", "role": "reviewer",
                "approved_profile": profile, "reason_code": "INDEPENDENT_EVIDENCE_GAIN",
                "selection_scorecard": selection, "review_assignment": assignment}
        args.update(overrides)
        result = budget.record_decision(self.ledger, **args)
        budget.bind_review_attempt(self.ledger, dispatch_key=key, review_state_ref=sha("synthetic-review-state"),
                                   assignment=args["review_assignment"], native_dispatch_nonce=native_nonce)
        return result

    def reserve(self, key, profile="sol-low", host=None):
        return budget.reserve_budget(self.ledger, dispatch_key=key, host_dispatch_id=host or "host-" + key,
                                     approved_profile=profile, approval_basis="explicit-request", role="reviewer")

    def complete(self, reservation):
        state = budget.read_budget(self.ledger)
        child = "child-" + reservation["reservation_id"]
        if state["schema_version"] == "2.0":
            budget.mark_started(self.ledger, reservation_id=reservation["reservation_id"], agent_id=child)
            return budget.mark_completed(self.ledger, reservation_id=reservation["reservation_id"], outcome="PASS")
        key = state["decisions"][reservation["dispatch_ref"]]["review_assignment"]["reviewer"] if reservation["role"] == "reviewer" else next(
            "worker-" + str(i) for i in range(5) if budget.sha256_ref("worker-" + str(i)) == reservation["dispatch_ref"])
        budget.record_host_dispatch_receipt(self.ledger, dispatch_key=key, host_dispatch_id="host-" + key, agent_id=child)
        budget.record_host_agent_observation(self.ledger, agent_id=child, phase="start")
        return budget.record_host_agent_observation(self.ledger, agent_id=child, phase="stop", outcome="PASS")

    def test_extension_keeps_base_role_caps_and_fits_two_astra_attempts(self):
        state = self.init()
        self.assertEqual("3.0", state["schema_version"])
        self.assertEqual(104, state["limits"]["max_units"])
        self.assertEqual(32, state["role_limits"]["worker"]["max_units"])
        self.assertEqual(32, state["role_limits"]["explorer"]["max_units"])
        self.decision("medium", "astra-medium")
        self.complete(self.reserve("medium", "astra-medium"))
        self.decision("high", "astra-high")
        self.complete(self.reserve("high", "astra-high"))
        state = budget.read_budget(self.ledger)
        self.assertEqual(72, state["usage"]["extension_units"])
        self.assertEqual(0, state["usage"]["base_units"])
        self.assertEqual(2, state["usage"]["premium_dispatches"])
        self.assertEqual(32, state["remaining_units"])
        self.decision("third", "sol-low")
        before = self.ledger.read_bytes()
        with self.assertRaises(budget.DelegationBudgetError):
            self.reserve("third")
        self.assertEqual(before, self.ledger.read_bytes())

    def test_premium_parallel_cap_is_atomic_even_with_plenty_of_units(self):
        self.init()
        self.decision("left")
        self.decision("right")

        def attempt(key):
            try:
                self.reserve(key)
                return "reserved"
            except budget.DelegationBudgetError:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("left", "right")))
        self.assertEqual(["denied", "reserved"], sorted(results))
        self.assertEqual(1, budget.read_budget(self.ledger)["usage"]["premium_active"])

    def test_one_permit_has_one_host_claim_and_replay_is_idempotent(self):
        self.init()
        self.decision("one")
        first = self.reserve("one")
        before = self.ledger.read_bytes()
        replay = self.reserve("one")
        self.assertEqual(first["reservation_id"], replay["reservation_id"])
        self.assertTrue(replay["idempotent"])
        with self.assertRaises(budget.DelegationBudgetError):
            self.reserve("one", host="different-host-call")
        self.assertEqual(before, self.ledger.read_bytes())

    def test_one_permit_cannot_be_owned_by_two_review_states(self):
        self.init()
        decision = self.decision("owner")
        before = self.ledger.read_bytes()
        with self.assertRaises(budget.DelegationBudgetError):
            budget.bind_review_attempt(self.ledger, dispatch_key="owner", review_state_ref=sha("another-state"),
                                       assignment=decision["review_assignment"])
        self.assertEqual(before, self.ledger.read_bytes())

    def test_release_refunds_units_but_not_attempts_and_never_reopens_permit(self):
        self.init()
        self.decision("cancelled")
        item = self.reserve("cancelled")
        before = self.ledger.read_bytes()
        with self.assertRaises(budget.DelegationBudgetError):
            budget.release_not_started(self.ledger, reservation_id=item["reservation_id"], proof_ref=sha("synthetic-no-start"))
        self.assertEqual(before, self.ledger.read_bytes())
        receipt = budget.record_host_dispatch_receipt(self.ledger, dispatch_key="cancelled",
                                                      host_dispatch_id="host-cancelled", disposition="not-started")
        budget.release_not_started(self.ledger, reservation_id=item["reservation_id"], proof_ref=receipt["proof_ref"])
        before = self.ledger.read_bytes()
        with self.assertRaises(budget.DelegationBudgetError):
            budget.mark_started(self.ledger, reservation_id=item["reservation_id"], agent_id="late-child")
        with self.assertRaises(budget.DelegationBudgetError):
            budget.record_host_dispatch_receipt(self.ledger, dispatch_key="cancelled",
                                                host_dispatch_id="host-cancelled", agent_id="late-child")
        self.assertEqual(before, self.ledger.read_bytes())
        state = budget.read_budget(self.ledger)
        self.assertEqual(0, state["usage"]["units"])
        self.assertEqual(1, state["usage"]["premium_dispatches"])
        self.assertEqual(1, state["usage"]["dispatches"])
        with self.assertRaises(budget.DelegationBudgetError):
            self.reserve("cancelled")
        with self.assertRaises(budget.DelegationBudgetError):
            self.reserve("cancelled", host="retry-host")
        self.decision("retry")
        self.complete(self.reserve("retry"))
        self.assertEqual(2, budget.read_budget(self.ledger)["usage"]["premium_dispatches"])

    def test_general_work_cannot_consume_review_extension(self):
        self.init("STANDARD")
        for index in range(5):
            key = "worker-" + str(index)
            budget.record_decision(self.ledger, dispatch_key=key, decision="DELEGATE", role="worker",
                                   approved_profile="terra-medium", reason_code="SEMANTIC_COMPLEXITY")
            if index == 4:
                with self.assertRaises(budget.DelegationBudgetError):
                    budget.reserve_budget(self.ledger, dispatch_key=key, host_dispatch_id="host-" + key,
                                          approved_profile="terra-medium", approval_basis="explicit-request", role="worker")
            else:
                item = budget.reserve_budget(self.ledger, dispatch_key=key, host_dispatch_id="host-" + key,
                                             approved_profile="terra-medium", approval_basis="explicit-request", role="worker")
                self.complete(item)
        self.assertEqual(16, budget.read_budget(self.ledger)["usage"]["base_units"])

    def test_invalid_assignment_identity_score_or_role_cannot_append(self):
        self.init()
        before = self.ledger.read_bytes()
        for overrides in ({"role": "worker"}, {"selection_scorecard": {}},
                          {"review_assignment": {}}, {"approved_profile": "sol-high"}):
            with self.assertRaises((budget.DelegationBudgetError, TypeError)):
                self.decision("bad", **overrides)
            self.assertEqual(before, self.ledger.read_bytes())
        self.decision("valid")
        with self.assertRaises(budget.DelegationBudgetError):
            budget.reserve_budget(self.ledger, dispatch_key="valid", host_dispatch_id="implicit")

    def test_light_extension_and_unbound_new_root_reject_before_creation(self):
        with self.assertRaises(budget.DelegationBudgetError):
            self.init("LIGHT")
        self.assertFalse(self.ledger.exists())
        self.binding = {}
        with self.assertRaises(budget.DelegationBudgetError):
            self.init()
        self.assertFalse(self.ledger.exists())

    def test_v2_writer_finishes_using_original_schema_and_costs(self):
        self.init(policy_id=LEGACY_POLICY_ID)
        budget.record_decision(self.ledger, dispatch_key="legacy", decision="DELEGATE", role="reviewer",
                               approved_profile="terra-medium", reason_code="SEMANTIC_COMPLEXITY")
        item = budget.reserve_budget(self.ledger, dispatch_key="legacy", host_dispatch_id="legacy-host",
                                     approved_profile="terra-medium", approval_basis="explicit-request", role="reviewer")
        self.complete(item)
        state = budget.close_budget(self.ledger, conclusion="PASS")
        self.assertEqual("2.0", state["schema_version"])
        self.assertEqual(4, state["usage"]["units"])
        records = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        self.assertEqual({"2.0"}, {item["schema_version"] for item in records})
        self.assertTrue(all("selection_scorecard" not in row["data"] for row in records))

    def test_unknown_version_and_changed_policy_digest_fail_without_writes(self):
        self.init()
        first = json.loads(self.ledger.read_text())
        for changed in ("future", "wrong-digest"):
            value = copy.deepcopy(first)
            if changed == "future":
                value["schema_version"] = "99.0"
            else:
                value["data"]["policy_digest"] = sha("wrong-policy")
            unsigned = {key: item for key, item in value.items() if key not in {"record_hash", "previous_hash"}}
            value["record_hash"] = budget._record_hash(value["previous_hash"], unsigned)
            self.ledger.write_text(json.dumps(value) + "\n", encoding="utf-8")
            before = self.ledger.read_bytes()
            with self.assertRaises(budget.DelegationBudgetError):
                budget.close_budget(self.ledger, conclusion="PASS")
            self.assertEqual(before, self.ledger.read_bytes())

    def test_pending_or_running_attempt_cannot_be_closed_as_pass(self):
        self.init()
        self.decision("pending")
        item = self.reserve("pending")
        with self.assertRaises(budget.DelegationBudgetError):
            budget.close_budget(self.ledger, conclusion="PASS")
        budget.record_host_dispatch_receipt(self.ledger, dispatch_key="pending", host_dispatch_id="host-pending", agent_id="child")
        budget.record_host_agent_observation(self.ledger, agent_id="child", phase="start")
        with self.assertRaises(budget.DelegationBudgetError):
            budget.close_budget(self.ledger, conclusion="PASS")
        self.assertFalse(budget.close_budget(self.ledger, conclusion="PARTIAL")["association_complete"])

    def test_v3_direct_lifecycle_api_and_legacy_events_cannot_forge_completion(self):
        self.init()
        self.decision("one")
        item = self.reserve("one")
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(budget.DelegationBudgetError, "V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS"):
            budget.mark_started(self.ledger, reservation_id=item["reservation_id"], agent_id="foreign-child")
        with self.assertRaisesRegex(budget.DelegationBudgetError, "V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS"):
            budget.mark_completed(self.ledger, reservation_id=item["reservation_id"], outcome="PASS")
        self.assertEqual(before, self.ledger.read_bytes())
        records = [json.loads(line) for line in before.decode().splitlines()]
        state = budget.read_budget(self.ledger)
        event = budget._state_event(state, "AGENT_STARTED", "synthetic-forged-start", {
            "reservation_id":item["reservation_id"],"agent_ref":sha("foreign-child"),"association":"reservation-id"
        }, len(records) + 1, records[-1]["record_hash"])
        with self.assertRaisesRegex(budget.DelegationBudgetError, "V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS"):
            budget._replay(records + [event])

    def test_native_receipt_start_stop_join_is_order_independent_and_idempotent(self):
        for order in itertools.permutations(("receipt", "start", "stop")):
            with self.subTest(order=order):
                self.ledger = self.root / ("-".join(order) + ".jsonl")
                self.init()
                self.decision("one")
                item = self.reserve("one")
                actions = {
                    "receipt": lambda: budget.record_host_dispatch_receipt(
                        self.ledger, host_dispatch_id="host-one", dispatch_key="one", agent_id="child-one"),
                    "start": lambda: budget.record_host_agent_observation(self.ledger, agent_id="child-one", phase="start"),
                    "stop": lambda: budget.record_host_agent_observation(self.ledger, agent_id="child-one", phase="stop", outcome="PASS"),
                }
                for phase in order:
                    actions[phase]()
                    before = self.ledger.read_bytes()
                    self.assertTrue(actions[phase]()["idempotent"])
                    self.assertEqual(before, self.ledger.read_bytes())
                state = budget.read_budget(self.ledger)
                self.assertEqual("COMPLETED", state["reservations"][item["reservation_id"]]["state"])
                self.assertTrue(state["association_complete"])
                before = self.ledger.read_bytes()
                with self.assertRaises(budget.DelegationBudgetError):
                    budget.record_host_agent_observation(self.ledger, agent_id="child-one", phase="stop", outcome="FAILED")
                self.assertEqual(before, self.ledger.read_bytes())

    def test_receipts_do_not_join_unknown_agents_or_reassign_one_child(self):
        self.init()
        for key in ("one", "two"):
            self.decision(key, "luna-low")
            self.reserve(key, "luna-low")
        budget.record_host_agent_observation(self.ledger, agent_id="unknown", phase="start")
        budget.record_host_dispatch_receipt(self.ledger, dispatch_key="one", host_dispatch_id="host-one", agent_id="child-one")
        self.assertTrue(all(item["state"] == "RESERVED" for item in budget.read_budget(self.ledger)["reservations"].values()))
        before = self.ledger.read_bytes()
        with self.assertRaises(budget.DelegationBudgetError):
            budget.record_host_dispatch_receipt(self.ledger, dispatch_key="two", host_dispatch_id="host-two", agent_id="child-one")
        with self.assertRaises(budget.DelegationBudgetError):
            budget.record_host_dispatch_receipt(self.ledger, dispatch_key="two", host_dispatch_id="host-one", agent_id="child-two")
        self.assertEqual(before, self.ledger.read_bytes())
        budget.record_host_dispatch_receipt(self.ledger, dispatch_key="two", host_dispatch_id="host-two", agent_id="child-two")
        budget.record_host_agent_observation(self.ledger, agent_id="child-two", phase="start")
        state = budget.read_budget(self.ledger)
        self.assertEqual(["RESERVED", "STARTED"], [item["state"] for item in state["reservations"].values()])

    def test_native_reservation_race_claims_one_permit_and_rejects_after_receipt(self):
        self.init()
        self.decision("one", "luna-low", native_dispatch_nonce="a" * 64)
        def attempt(host):
            try:
                return budget.reserve_native_review(self.ledger, host_dispatch_id=host, approved_profile="luna-low",
                                                    agent_type=ROLE, baseline_sha256=CONTEXT["baseline_sha256"],
                                                    native_dispatch_nonce="a" * 64)
            except budget.DelegationBudgetError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("host-a", "host-b")))
        self.assertEqual(1, sum(item is not None for item in results))
        winning_host = "host-a" if results[0] else "host-b"
        self.assertTrue(attempt(winning_host)["idempotent"])
        budget.record_host_dispatch_receipt(self.ledger, host_dispatch_id=winning_host, agent_id="native-child")
        self.assertIsNone(attempt(winning_host))
        self.assertEqual(1, budget.read_budget(self.ledger)["usage"]["dispatches"])

    def test_native_references_select_exact_permits_and_cannot_be_rebound(self):
        self.init()
        for key, nonce in (("one", "a" * 64), ("two", "b" * 64)):
            self.decision(key, "luna-low", native_dispatch_nonce=nonce)
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(budget.DelegationBudgetError, "REFERENCE_REUSED"):
            assignment = budget.read_budget(self.ledger)["decisions"][sha("two")]["review_assignment"]
            records = [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]
            claims = [item for item in records if item["event_type"] == "REVIEW_ATTEMPT_BOUND"]
            claims[-1]["data"]["native_dispatch_ref"] = claims[0]["data"]["native_dispatch_ref"]
            budget._replay(records)
        with self.assertRaises(budget.DelegationBudgetError):
            budget.bind_review_attempt(self.ledger, dispatch_key="two", review_state_ref=sha("synthetic-review-state"),
                                       assignment=assignment, native_dispatch_nonce="a" * 64)
        self.assertEqual(before, self.ledger.read_bytes())
        for key, nonce in (("two", "b" * 64), ("one", "a" * 64)):
            item = budget.reserve_native_review(self.ledger, host_dispatch_id="host-" + key, approved_profile="luna-low",
                                                agent_type=ROLE, baseline_sha256=CONTEXT["baseline_sha256"],
                                                native_dispatch_nonce=nonce)
            self.assertEqual(sha(key), item["dispatch_ref"])
        self.assertEqual(2, budget.read_budget(self.ledger)["usage"]["dispatches"])

    def test_replay_rejects_two_permits_bound_to_the_same_host_call(self):
        self.init()
        for name in ("one", "two"):
            self.decision(name, "luna-low")
            self.reserve(name, "luna-low")
        records = [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]
        reservation_events = [row for row in records if row["event_type"] == "BUDGET_RESERVED"]
        reservation_events[-1]["data"]["host_dispatch_ref"] = reservation_events[0]["data"]["host_dispatch_ref"]
        with self.assertRaisesRegex(budget.DelegationBudgetError,"V3_HOST_CALL_ALREADY_BOUND"):
            budget._replay(records)


if __name__ == "__main__":
    unittest.main()
