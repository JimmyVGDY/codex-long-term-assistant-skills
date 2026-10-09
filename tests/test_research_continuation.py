"""中文：历史承接不得冒充新的本地复审或通过的完整研究。

English: Historical carries cannot masquerade as a new local review or a PASS campaign.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4, budget_v5 as budget
from cp_runtime.routing_context_contract import CONTEXT_64K, ISOLATED_PHASES_V2, MODE_V2, runtime
from cp_runtime.routing_contract import ref
import test_routing_v4_context as fixtures


class HistoricalCarryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContextTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        old = budget_v4.read_budget(self.fixture.path)
        trial_ref = ref("one-original-frozen-trial")
        self.slot_id = "trial_" + trial_ref[7:59]
        self.trial_ref = trial_ref
        self.path = self.fixture.root / "continuation-budget.jsonl"
        plan = copy.deepcopy(old["phase_plan"])
        plan["slots"][0]["slot_id"] = self.slot_id
        rt = runtime(ROOT / "hooks/review_context_reader.py", Path(sys.executable),
                     transport_mode=MODE_V2, context_profile=CONTEXT_64K,
                     evaluation_contract=ISOLATED_PHASES_V2,
                     delivery_contract="same-call-notify/2")
        rt["research_contract"] = "desktop-research-campaign/1"
        binding = {**old["root_binding"], "schema_version": "dispatch-root/3",
                   "context_runtime": rt}
        identity = {**old["identity"], "budget_id": "carry-test",
                    "task_id": "new-continuation-root"}
        budget.initialize(self.path, declared_identity=identity, root_binding=binding,
                          sources=old["sources"], execution_mode="EVALUATION",
                          capacity=old["capacity"], role_capacity=old["role_capacity"],
                          phase_capacity=old["phase_capacity"], phase_plan=plan,
                          max_parallel=1, max_depth=1)
        state = budget.read_budget(self.path)
        self.data = {"slot_id": self.slot_id, "trial_ref": trial_ref,
                     "profile_id": plan["slots"][0]["options"][0]["profile_id"],
                     "scenario_ref": ref(plan["slots"][0]["scenario"]),
                     "source_ledger_path": str(self.fixture.path),
                     "source_ledger_head_hash": "a" * 64,
                     "source_project_id": identity["project_id"],
                     "source_repo_fingerprint": identity["repo_fingerprint"],
                     "source_task_id": "old-root",
                     "source_reservation_id": "DBR5_prior",
                     "source_result_ref": ref("prior-incomplete-result"),
                     "source_grade_ref": "",
                     "source_evidence_ref": ref("prior-capacity-proof"),
                     "carry_evidence_ref": ref("carry-proof"),
                     "carry_evidence_path": str(self.fixture.root / "carry-proof.json"),
                     "disposition": "HOST_INFRA_UNGRADED"}

    def append(self, data):
        with budget.OwnerTokenLock(self.path, timeout=2):
            events = budget._read_events(self.path)
            state = budget.replay(events)
            return budget._append(self.path, events,
                budget._event(state, state["identity"], "HISTORICAL_ATTEMPT_CARRIED", data))

    def test_infra_carry_is_accounted_without_local_call_and_cannot_close_pass(self):
        state = self.append(self.data)
        self.assertEqual("SATISFIED", state["phase_plan"]["slots"][0]["status"])
        self.assertEqual({}, state["reservations"])
        self.assertEqual({}, state["permits"])
        self.assertEqual(0, budget._usage(state)["resources"]["attempts"])
        with self.assertRaisesRegex(ValueError, "V5_CLOSE_HISTORICAL_INFRA_FAILURE"):
            budget.close(self.path, outcome="PASS", evidence_ref=ref("not-a-model-result"))
        self.assertEqual("PARTIAL", budget.close(self.path,
            outcome="PARTIAL", evidence_ref=ref("honest-capacity-history"))["outcome"])

    def test_reader_denial_carry_remains_ungraded_and_cannot_close_pass(self):
        data = {**self.data, "disposition": "READER_PROTOCOL_UNGRADED",
                "source_evidence_ref": ref("reader-denial-proof")}
        state = self.append(data)
        self.assertEqual("READER_PROTOCOL_UNGRADED",
                         state["historical_carries"][self.slot_id]["disposition"])
        self.assertEqual(0, budget._usage(state)["resources"]["attempts"])
        with self.assertRaisesRegex(ValueError, "V5_CLOSE_HISTORICAL_INFRA_FAILURE"):
            budget.close(self.path, outcome="PASS", evidence_ref=ref("no-grade"))
        self.assertEqual("PARTIAL", budget.close(self.path, outcome="PARTIAL",
            evidence_ref=ref("reader-gap"))["outcome"])

    def test_duplicate_and_foreign_or_mismatched_carry_are_denied(self):
        variants = []
        for field, value in (("source_project_id", "foreign-project"),
                             ("source_repo_fingerprint", ref("foreign-repo")),
                             ("profile_id", "g6-astra-low"),
                             ("trial_ref", ref("other-trial"))):
            modified = {**self.data, field: value}
            variants.append(modified)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.append(data)
        state = self.append(self.data)
        with self.assertRaises(ValueError):
            self.append(self.data)
        self.assertEqual(1, len(budget.read_budget(self.path)["historical_carries"]))


if __name__ == "__main__":
    unittest.main()
