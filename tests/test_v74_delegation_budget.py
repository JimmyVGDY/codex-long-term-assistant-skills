from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from cp_runtime.delegation_budget import (  # noqa: E402
    DelegationBudgetError, canonical_json, close_budget, initialize_budget, mark_completed,
    mark_started, read_budget, record_decision, release_not_started, reserve_budget,
    sha256_ref,
)

FINGERPRINT = "sha256:" + "a" * 64
PROOF = "sha256:" + "b" * 64


class DelegationBudgetV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temp.name) / "delegation-budget-v2.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def init(self, budget_class: str = "STANDARD", default: str = "luna-medium") -> dict:
        return initialize_budget(
            self.ledger, budget_id="BUDGET-1", task_id="TASK-1", project_id="project-1",
            repo_fingerprint=FINGERPRINT, budget_class=budget_class,
            default_dispatch_profile=default,
        )

    def decide(self, key: str, role: str = "reviewer", profile: str = "luna-low", **extra: object) -> dict:
        return record_decision(
            self.ledger, dispatch_key=key, decision="DELEGATE", role=role,
            approved_profile=profile, reason_code=str(extra.pop("reason_code", "INDEPENDENT_EVIDENCE_GAIN")),
            **extra,
        )

    def test_three_roles_share_root_units_and_no_refund_after_start(self) -> None:
        self.init("STANDARD")
        reservations = []
        for index, role in enumerate(("reviewer", "explorer", "worker"), 1):
            key = "dispatch-%d" % index
            self.decide(key, role=role, profile="luna-medium")
            reservation = reserve_budget(self.ledger, dispatch_key=key, host_dispatch_id="tool-%d" % index,
                                         approved_profile="luna-medium", approval_basis="explicit-request")
            reservations.append(reservation["reservation_id"])
            mark_started(self.ledger, reservation_id=reservation["reservation_id"], agent_id="agent-%d" % index)
            mark_completed(self.ledger, reservation_id=reservation["reservation_id"], outcome="PASS")
        state = read_budget(self.ledger)
        self.assertEqual(6, state["usage"]["units"])
        self.assertEqual(3, state["usage"]["dispatches"])
        self.assertEqual(0, state["usage"]["active"])
        self.assertEqual({role: 1 for role in ("reviewer", "explorer", "worker")},
                         {role: state["usage"]["by_role"][role]["dispatches"] for role in state["usage"]["by_role"]})
        with self.assertRaises(DelegationBudgetError):
            release_not_started(self.ledger, reservation_id=reservations[0], proof_ref=PROOF)

    def test_policy_default_is_charged_from_approved_profile(self) -> None:
        self.init("STANDARD", "terra-medium")
        self.decide("policy-default", profile="terra-medium")
        result = reserve_budget(self.ledger, dispatch_key="policy-default", host_dispatch_id="tool-default",
                                approved_profile="", approval_basis="policy-default")
        self.assertEqual(4, result["units"])
        item = read_budget(self.ledger)["reservations"][result["reservation_id"]]
        self.assertEqual("policy-default", item["approval_basis"])
        self.assertEqual("terra-medium", item["approved_profile"])
        self.assertNotIn("actual_profile", item)

    def test_route_contract_blocks_missing_evidence_escalation_and_skipped_tier(self) -> None:
        self.init("STANDARD", "luna-medium")
        with self.assertRaises(DelegationBudgetError):
            self.decide("missing", profile="terra-medium", reason_code="MISSING_EVIDENCE")
        with self.assertRaises(DelegationBudgetError):
            self.decide("skip", profile="terra-high", reason_code="LOWER_TIER_INCONCLUSIVE",
                        prior_profile="luna-medium", prior_result_ref=PROOF)
        direct = self.decide("security", profile="terra-high", reason_code="SECURITY_OR_CONCURRENCY_RISK",
                             risk_domain="SECURITY", difficulty="HIGH")
        self.assertEqual("terra-high", direct["approved_profile"])

    def test_parallel_reservation_is_atomic_and_idempotent(self) -> None:
        self.init("LIGHT", "luna-low")
        for index in range(2):
            self.decide("parallel-%d" % index, role="worker", profile="luna-low")

        def attempt(index: int) -> str:
            try:
                reserve_budget(self.ledger, dispatch_key="parallel-%d" % index,
                               host_dispatch_id="parallel-tool-%d" % index,
                               approved_profile="luna-low", approval_basis="explicit-request")
                return "ok"
            except DelegationBudgetError:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertEqual(1, outcomes.count("ok"))
        self.assertEqual(1, read_budget(self.ledger)["usage"]["dispatches"])
        winner = outcomes.index("ok")
        again = reserve_budget(self.ledger, dispatch_key="parallel-%d" % winner,
                               host_dispatch_id="parallel-tool-%d" % winner,
                               approved_profile="luna-low", approval_basis="explicit-request")
        self.assertTrue(again["idempotent"])

    def test_nested_depth_uses_root_budget(self) -> None:
        self.init("STANDARD", "luna-low")
        self.decide("parent", role="worker")
        parent = reserve_budget(self.ledger, dispatch_key="parent", host_dispatch_id="parent-tool",
                                approved_profile="luna-low", approval_basis="explicit-request")
        mark_started(self.ledger, reservation_id=parent["reservation_id"], agent_id="parent-agent")
        self.decide("child", role="explorer", parent_reservation_id=parent["reservation_id"])
        child = reserve_budget(self.ledger, dispatch_key="child", host_dispatch_id="child-tool",
                               approved_profile="luna-low", approval_basis="explicit-request")
        self.assertEqual(2, child["depth"])
        with self.assertRaises(DelegationBudgetError):
            self.decide("grandchild", role="reviewer", parent_reservation_id=child["reservation_id"])

    def test_only_host_proof_releases_unstarted_reservation(self) -> None:
        self.init("LIGHT", "luna-low")
        self.decide("release", role="explorer")
        reserved = reserve_budget(self.ledger, dispatch_key="release", host_dispatch_id="release-tool",
                                  approved_profile="luna-low", approval_basis="explicit-request")
        released = release_not_started(self.ledger, reservation_id=reserved["reservation_id"], proof_ref=PROOF)
        self.assertEqual("NOT_STARTED_RELEASED", released["state"])
        self.assertEqual(0, read_budget(self.ledger)["usage"]["units"])
        self.assertTrue(release_not_started(self.ledger, reservation_id=reserved["reservation_id"], proof_ref=PROOF)["idempotent"])

    def test_start_cannot_change_pre_reserved_cost(self) -> None:
        self.init("STANDARD", "luna-low")
        self.decide("actual", role="worker", profile="terra-medium")
        reservation = reserve_budget(self.ledger, dispatch_key="actual", host_dispatch_id="actual-tool",
                                     approved_profile="terra-medium", approval_basis="explicit-request")
        started = mark_started(self.ledger, reservation_id=reservation["reservation_id"], agent_id="agent-actual")
        self.assertFalse(started["violated"])
        self.assertEqual(4, read_budget(self.ledger)["usage"]["units"])
        self.assertNotIn("actual_profile", self.ledger.read_text(encoding="utf-8"))

    def test_host_attestation_input_is_not_an_accepted_start_argument(self) -> None:
        self.init("LIGHT", "luna-low")
        self.decide("topup", role="worker", profile="luna-low")
        reservation = reserve_budget(self.ledger, dispatch_key="topup", host_dispatch_id="topup-tool",
                                     approved_profile="luna-low", approval_basis="explicit-request")
        with self.assertRaises(TypeError):
            mark_started(self.ledger, reservation_id=reservation["reservation_id"], agent_id="agent-topup",
                         actual_profile="terra-high")
        state = read_budget(self.ledger)
        self.assertFalse(state["violated"])
        self.assertEqual(1, state["usage"]["units"])

    def test_chain_tamper_and_cross_project_identity_fail_closed(self) -> None:
        self.init()
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0]); record["project_id"] = "other-project"
        self.ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaises(DelegationBudgetError):
            read_budget(self.ledger)

    def test_rehashed_unknown_event_data_field_fails_closed(self) -> None:
        self.init()
        record = json.loads(self.ledger.read_text(encoding="utf-8"))
        record["data"]["raw_prompt"] = "must-not-enter-ledger"
        unsigned = {key: value for key, value in record.items()
                    if key not in {"previous_hash", "record_hash"}}
        record["record_hash"] = hashlib.sha256(
            (record["previous_hash"] + "\n" + canonical_json(unsigned)).encode("utf-8")
        ).hexdigest()
        self.ledger.write_text(canonical_json(record) + "\n", encoding="utf-8")
        with self.assertRaises(DelegationBudgetError):
            read_budget(self.ledger)

    def test_ledger_contains_no_dispatch_key_or_task_body(self) -> None:
        self.init()
        key = "opaque-dispatch-1"
        self.decide(key, role="explorer", responsibility="evidence-search")
        raw = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn(key, raw)
        self.assertIn(sha256_ref(key), raw)

    def test_close_does_not_claim_task_success(self) -> None:
        self.init()
        closed = close_budget(self.ledger, conclusion="UNKNOWN")
        self.assertTrue(closed["closed"])
        self.assertFalse(closed["violated"])
        with self.assertRaises(DelegationBudgetError):
            self.decide("closed", role="worker")

    def test_closed_budget_rejects_late_lifecycle_events_and_replay(self) -> None:
        self.init()
        self.decide("late", role="worker")
        reserved = reserve_budget(self.ledger, dispatch_key="late", host_dispatch_id="late-tool",
                                  approved_profile="luna-low", approval_basis="explicit-request")
        close_budget(self.ledger, conclusion="UNKNOWN")
        with self.assertRaises(DelegationBudgetError):
            mark_started(self.ledger, reservation_id=reserved["reservation_id"], agent_id="late-agent")
        with self.assertRaises(DelegationBudgetError):
            release_not_started(self.ledger, reservation_id=reserved["reservation_id"], proof_ref=PROOF)

        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        last = json.loads(lines[-1])
        data = {"reservation_id": reserved["reservation_id"], "outcome": "PASS"}
        unsigned = {
            "schema_version": "2.0", "event_id": "DBE_late", "event_type": "AGENT_COMPLETED",
            "captured_at": last["captured_at"], "sequence": last["sequence"] + 1,
            "budget_id": last["budget_id"], "task_id": last["task_id"],
            "project_id": last["project_id"], "repo_fingerprint": last["repo_fingerprint"],
            "data": data,
        }
        record = {**unsigned, "previous_hash": last["record_hash"]}
        record["record_hash"] = hashlib.sha256(
            (record["previous_hash"] + "\n" + canonical_json(unsigned)).encode("utf-8")
        ).hexdigest()
        self.ledger.write_text("\n".join(lines + [canonical_json(record)]) + "\n", encoding="utf-8")
        with self.assertRaises(DelegationBudgetError):
            read_budget(self.ledger)

if __name__ == "__main__":
    unittest.main()
