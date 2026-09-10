from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import test_capability_store as fixtures
except ModuleNotFoundError:
    from runtime.tests import test_capability_store as fixtures

from cp_runtime.capability_gate import GatePolicy
from cp_runtime.capability_operation import CapabilityOperation
from cp_runtime.capability_operation_workflow import OperationWorkflow
from cp_runtime import capability_operation_workflow as workflow_module
from cp_runtime.capability_index import scan
from cp_runtime.capability_store import CapabilityError
from cp_runtime.patch_intent import parse_apply_patch


class OperationWorkflowTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def operation(self, attempt: str = "attempt-a"):
        policy = GatePolicy(self.store, self.base / "gate-config")
        policy.set_enabled(True, None)
        operation = CapabilityOperation(policy, "session", "turn")
        command = ("*** Begin Patch\n*** Update File: app.py\n@@\n"
                   "-    return 1\n+    return 2\n*** End Patch\n")
        intent = parse_apply_patch(command, self.repo)
        origin = operation.create_or_replay_origin(
            attempt, intent, intent["target_paths"], intent,
        )
        return policy, operation, OperationWorkflow(operation), intent, origin

    @staticmethod
    def decisions(prepared):
        return [{"id": item["id"], "choice": "extend", "reason": "保持既有公开入口"}
                for item in prepared["required_decisions"]]

    def test_t29_full_a_prepare_b_posttool_finish_chain(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        self.assertEqual("READY", prepared["state"]["state"])
        self.assertIsNone(prepared["state"]["dispatch_tool_use_id"])
        claimed = operation.find_and_claim(
            tool_use_id="attempt-b", intent=intent,
            targets=intent["target_paths"], prestate=intent,
        )
        self.assertEqual("attempt-a", claimed["origin_attempt_id"])
        self.assertEqual("attempt-b", claimed["dispatch_tool_use_id"])
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(origin["operation_ref"], "attempt-b", {"ok": True},
                                  summary_code="RECEIVED")
        finished = workflow.finish(
            origin["operation_ref"], tool_use_id="attempt-b",
            decisions=self.decisions(prepared),
        )
        self.assertEqual("VERIFIED", finished["state"]["state"])
        self.assertEqual(["app.py"], finished["changed_paths"])
        self.assertTrue(workflow.check(origin["operation_ref"])["valid"])

    def test_t30_different_intent_does_not_consume_ready(self):
        _, operation, workflow, intent, origin = self.operation()
        workflow.prepare(origin["operation_ref"], term="public")
        other = dict(intent)
        other["command_sha256"] = "0" * 64
        other["intent_sha256"] = "1" * 64
        self.assertIsNone(operation.find_and_claim(
            tool_use_id="attempt-c", intent=other,
            targets=intent["target_paths"], prestate=other,
        ))
        self.assertEqual("READY", operation.check(origin["operation_ref"])["state"])

    def test_t31_prepare_requires_existing_hook_origin(self):
        policy = GatePolicy(self.store, self.base / "gate-config")
        policy.set_enabled(True, None)
        with self.assertRaisesRegex(CapabilityError, "OP_INVALID_OPERATION_REF"):
            CapabilityOperation.open(policy, "not-an-operation")

    def test_t32_missing_posttool_never_verifies(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        with self.assertRaisesRegex(CapabilityError, "OP_RESULT_PENDING_REQUIRED"):
            workflow.finish(origin["operation_ref"], tool_use_id="attempt-b",
                            decisions=self.decisions(prepared))
        self.assertNotEqual("VERIFIED", operation.check(origin["operation_ref"])["state"])

    def test_decisions_are_exact_and_unrelated_large_dirt_is_ignored(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        with (self.repo / "unrelated.bin").open("wb") as stream:
            stream.seek(9 * 1024 * 1024)
            stream.write(b"x")
        operation.record_posttool(origin["operation_ref"], "attempt-b", {"ok": True},
                                  summary_code="RECEIVED")
        if prepared["required_decisions"]:
            with self.assertRaisesRegex(CapabilityError, "OP_DECISIONS_INCOMPLETE"):
                workflow.finish(origin["operation_ref"], tool_use_id="attempt-b", decisions=[])
        result = workflow.finish(origin["operation_ref"], tool_use_id="attempt-b",
                                 decisions=self.decisions(prepared))
        self.assertEqual("VERIFIED", result["state"]["state"])

    def test_check_invalidates_stale_verified_evidence(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(origin["operation_ref"], "attempt-b", {"ok": True},
                                  summary_code="RECEIVED")
        workflow.finish(origin["operation_ref"], tool_use_id="attempt-b",
                        decisions=self.decisions(prepared))
        (self.repo / "app.py").write_text("def public():\n    return 3\n", encoding="utf-8")
        checked = workflow.check(origin["operation_ref"])
        self.assertFalse(checked["valid"])
        self.assertEqual("OUTCOME_UNKNOWN", checked["state"]["state"])

    def test_unrelated_index_update_does_not_invalidate_scoped_receipt(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(origin["operation_ref"], "attempt-b", {"ok": True},
                                  summary_code="RECEIVED")
        workflow.finish(origin["operation_ref"], tool_use_id="attempt-b",
                        decisions=self.decisions(prepared))
        (self.repo / "other.py").write_text("def unrelated():\n    return 1\n", encoding="utf-8")
        scan(self.store, ["other.py"])
        self.assertTrue(workflow.check(origin["operation_ref"])["valid"])

    def test_cancel_during_independent_index_maintenance_never_writes_finish_receipt(self):
        _, operation, workflow, intent, origin = self.operation()
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(origin["operation_ref"], "attempt-b", {"ok": True},
                                  summary_code="APPLY_PATCH_SUCCEEDED")
        original = workflow_module.invalidate

        def cancel_after_index(*args, **kwargs):
            result = original(*args, **kwargs)
            operation.cancel(origin["operation_ref"])
            return result

        with patch.object(workflow_module, "invalidate", side_effect=cancel_after_index):
            with self.assertRaisesRegex(CapabilityError, "OP_REVISION_CONFLICT"):
                workflow.finish(origin["operation_ref"], tool_use_id="attempt-b",
                                decisions=self.decisions(prepared))
        state = operation.check(origin["operation_ref"])
        self.assertEqual("OUTCOME_UNKNOWN", state["state"])
        self.assertIsNone(state["evidence"]["finish_sha256"])


if __name__ == "__main__":
    unittest.main()
