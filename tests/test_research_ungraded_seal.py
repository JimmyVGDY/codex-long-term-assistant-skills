"""中文：已创建但未评分的研究尝试保留费用，不阻塞其他槽。

English: A created, ungraded study attempt keeps its cost without blocking other slots.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v5 as budget, review_v5 as review, routing_hook_v5 as hook
from cp_runtime.routing_contract import ref
from cp_runtime.routing_contract import VECTOR_KEYS
from cp_runtime.routing_phase_plan import feasible_witness, validate_plan
import test_routing_context_transport_v2 as transport


class UngradedSealTests(unittest.TestCase):
    def setUp(self):
        self.fixture = transport.TransportV2Tests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.begin()
        tool = self.fixture.tool()
        hook.child_tool(self.fixture.path, tool)
        with self.assertRaisesRegex(ValueError, "OUTPUT_INTEGRITY"):
            hook.child_tool(self.fixture.path, {**tool, "hook_event_name": "PostToolUse",
                                                "tool_response": {"exit_code": 1, "output": ""}})
        self.fixture.final(payload={"status": "incomplete", "findings": [], "checked_scope": [],
                                    "unverified_items": ["reader denied"], "summary": "No verified material."},
                           stop=False)
        self.fixture.f.stop()
        review.record_failure_accounting(self.fixture.f.review_dir, self.fixture.f.pid,
                                         evidence_ref=ref("synthetic-reader-denial"))
        self.state = budget.read_budget(self.fixture.path)
        self.rid = next(iter(self.state["reservations"]))
        self.pid = self.fixture.f.pid
        self.trial_ref = ref("synthetic-frozen-trial")
        self.slot_id = "trial_" + self.trial_ref[7:59]
        old_slot = self.state["phase_plan"]["slots"][0]
        old_slot["slot_id"] = self.slot_id
        self.state["permits"][self.pid]["slot_id"] = self.slot_id
        self.state["permits"][self.pid]["request"]["slot_id"] = self.slot_id
        other = copy.deepcopy(old_slot)
        other.update(slot_id="trial_" + ref("another-frozen-trial")[7:59],
                     status="PENDING", active_reservation_ref="",
                     accepted_result_ref="", release_evidence_ref="")
        self.state["phase_plan"]["slots"].append(other)
        need = old_slot["options"][0]["resources"]
        for key in VECTOR_KEYS:
            self.state["capacity"][key] = 2 * need[key]
        self.state["role_capacity"]["reviewer"] = 2 * need["units"]
        self.state["phase_capacity"][old_slot["scenario"]["phase"]] = 2 * need["units"]
        runtime = self.state["root_binding"]["context_runtime"]
        runtime["research_contract"] = "desktop-research-campaign/2"
        runtime["context_profile"] = "bounded-review-64k/1"
        runtime["delivery_contract"] = "same-call-notify/2"
        runtime["evaluation_contract"] = "isolated-review-phases/2"
        self.data = {"slot_id": self.slot_id, "trial_ref": self.trial_ref,
                     "reservation_id": self.rid,
                     "accepted_result_ref": self.state["accepted_results"][self.rid]["result_ref"],
                     "evidence_ref": ref("verified-reader-denial"),
                     "evidence_path": str(self.fixture.f.f.root / "reader-denial.json"),
                     "reason_code": "READER_PROTOCOL_DENIED"}

    def apply(self, state, data, kind="EVALUATION_UNGRADED_SEALED"):
        event = budget._event(state, state["identity"], kind, data)
        return budget._apply(copy.deepcopy(state), event)

    def witness(self, state):
        available = budget.snapshot_budget(state)
        return feasible_witness(state["phase_plan"], available["remaining"],
                                role_capacity=available["role_capacity"],
                                phase_capacity=available["phase_capacity"])

    def test_terminal_incomplete_is_sealed_without_refund_and_next_slot_is_feasible(self):
        self.assertNotEqual("FEASIBLE", self.witness(self.state)["status"])
        updated = self.apply(self.state, self.data)
        self.assertEqual("UNGRADABLE", budget._slot(updated, self.slot_id)["status"])
        self.assertEqual(1, budget._usage(updated)["resources"]["attempts"])
        self.assertEqual(self.state["phase_plan"]["slots"][0]["options"][0]["resources"]["units"],
                         budget._usage(updated)["resources"]["units"])
        self.assertEqual("FEASIBLE", self.witness(updated)["status"])
        with self.assertRaisesRegex(ValueError, "CLOSE_UNFULFILLED_SCOPE"):
            self.apply(updated, {"outcome": "PASS", "evidence_ref": ref("not-clean")}, "CLOSED")
        self.assertEqual("PARTIAL", self.apply(updated,
            {"outcome": "PARTIAL", "evidence_ref": ref("honest-gap")}, "CLOSED")["outcome"])
        unproven = copy.deepcopy(updated["phase_plan"])
        unproven["slots"][0]["release_evidence_ref"] = ""
        with self.assertRaisesRegex(ValueError, "PHASE_UNGRADABLE_PROOF_REQUIRED"):
            validate_plan(unproven)
        with self.assertRaisesRegex(ValueError, "RESEARCH_UNGRADABLE_CANNOT_INITIALIZE"):
            budget.initialize(self.fixture.f.f.root / "forged-initial-ungradable.jsonl",
                declared_identity={**updated["identity"], "budget_id": "forged-ungradable"},
                root_binding=updated["root_binding"], sources=updated["sources"],
                execution_mode="EVALUATION", capacity=updated["capacity"],
                role_capacity=updated["role_capacity"], phase_capacity=updated["phase_capacity"],
                phase_plan=updated["phase_plan"], max_parallel=1, max_depth=1)

    def test_foreign_duplicate_delivered_or_uncreated_seals_are_denied(self):
        variants = []
        for key, value in (("trial_ref", ref("wrong-trial")),
                           ("accepted_result_ref", ref("invented-review")),
                           ("reason_code", "UNVERIFIED")):
            variants.append((self.state, {**self.data, key: value}))
        legacy = copy.deepcopy(self.state)
        legacy["root_binding"]["context_runtime"]["research_contract"] = "desktop-research-campaign/1"
        variants.append((legacy, self.data))
        delivered = copy.deepcopy(self.state)
        delivered["context_deliveries"][self.rid] = {"output_ref": ref("material")}
        variants.append((delivered, self.data))
        uncreated = copy.deepcopy(self.state)
        uncreated["host_receipts"][self.rid]["disposition"] = "not-started"
        variants.append((uncreated, self.data))
        for state, data in variants:
            with self.subTest(data=data, contract=state["root_binding"]["context_runtime"]["research_contract"]), self.assertRaises(ValueError):
                self.apply(state, data)
        sealed = self.apply(self.state, self.data)
        with self.assertRaises(ValueError):
            self.apply(sealed, self.data)


if __name__ == "__main__":
    unittest.main()
