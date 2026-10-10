"""中文：实际写入门禁的继续执行与安全回归。

English: Continuation and safety regressions for the actual Desktop write gate.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cp_runtime.patch_intent import PatchIntentError, parse_apply_patch, revalidate_intent
from cp_runtime import capability_gate_hook as gate
from cp_runtime.capability_store import CapabilityError
from cp_runtime.gate_contract import registration_inventory
from cp_runtime import capability_operation_workflow as workflow_module
import test_capability_operation_workflow as workflow_tests


class DesktopPatchPathTests(unittest.TestCase):
    def test_absolute_path_inside_repository_is_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "value.txt"
            target.write_text("old\n", encoding="utf-8")
            command = ("*** Begin Patch\n*** Update File: " + target.as_posix()
                       + "\n@@\n-old\n+new\n*** End Patch\n")
            intent = parse_apply_patch(command, root)
            self.assertEqual(intent["target_paths"], ["value.txt"])
            self.assertTrue(revalidate_intent(intent, root))

    def test_absolute_path_outside_repository_remains_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            command = ("*** Begin Patch\n*** Add File: "
                       + (root.parent / "outside.txt").as_posix()
                       + "\n+value\n*** End Patch\n")
            with self.assertRaisesRegex(PatchIntentError, "PATH_ESCAPE"):
                parse_apply_patch(command, root)

    def test_absolute_sensitive_path_remains_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = ("*** Begin Patch\n*** Add File: "
                       + (root / ".git" / "config").as_posix()
                       + "\n+value\n*** End Patch\n")
            with self.assertRaisesRegex(PatchIntentError, "SENSITIVE_PATH"):
                parse_apply_patch(command, root)


class DesktopGateContractTests(unittest.TestCase):
    def test_supported_optional_host_metadata_does_not_reject_patch(self):
        event = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
                 "tool_use_id": "call", "session_id": "session", "turn_id": "turn",
                 "cwd": "/repo", "tool_input": {"command": "patch"},
                 "agent_transcript_path": "/transcript", "stop_hook_active": False}
        self.assertEqual(gate._canonical_patch(event)[0], "call")
        self.assertEqual(gate._canonical_patch({**event, "duration_ms": 0,
                                               "trace_label": "future-metadata"})[0], "call")
        with self.assertRaisesRegex(CapabilityError, "OP_CANONICAL_INPUT"):
            gate._canonical_patch({**event, "toolName": "other"})

    def test_path_error_is_not_reported_as_missing_origin(self):
        with patch.object(gate, "locate_policy", side_effect=CapabilityError("PATH_ESCAPE")):
            result = gate._v2_patch(Path("/runtime"), {"cwd": "/repo"}, "PreToolUse")
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("PATH_ESCAPE", reason)
        self.assertIn("STOP_AFFECTED_ACTION", reason)
        self.assertNotIn("LEGACY_WRITE_ORIGIN_UNAVAILABLE", reason)

    def test_unknown_installer_command_cannot_hide_as_external(self):
        hooks = {"PreToolUse": [{"hooks": [{"command": "python renamed_gate.py"}]}]}
        with self.assertRaisesRegex(ValueError, "UNMAPPED_MANAGED_GATE_ENTRYPOINT"):
            registration_inventory(hooks)
        self.assertEqual(registration_inventory(hooks, source="account")[0]["scope"], "external")
        hooks["PreToolUse"][0]["hooks"][0]["command"] = "python /cp-assistant-hooks/renamed_gate.py"
        with self.assertRaisesRegex(ValueError, "UNMAPPED_MANAGED_GATE_ENTRYPOINT"):
            registration_inventory(hooks, source="account")


class DesktopIndexDegradationTests(unittest.TestCase):
    setUp = workflow_tests.OperationWorkflowTests.setUp
    tearDown = workflow_tests.OperationWorkflowTests.tearDown
    operation = workflow_tests.OperationWorkflowTests.operation

    def test_partial_index_does_not_block_valid_native_operation(self):
        _, operation, workflow, intent, origin = self.operation()
        with patch.object(workflow_module, "scan", return_value={"coverage": {"complete": False}}):
            prepared = workflow.prepare(origin["operation_ref"])
        self.assertEqual(prepared["state"]["state"], "READY")
        self.assertEqual(prepared["gate_decision"]["decision"], "CONTINUE_DEGRADED")
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(origin["operation_ref"], "attempt-b", "Done!")
        result = workflow.finish(origin["operation_ref"], tool_use_id="attempt-b", decisions=[])
        self.assertEqual(result["index_verification"], "UNVERIFIED")
        self.assertTrue(workflow.check(origin["operation_ref"])["valid"])

    def test_corrupt_index_is_not_consumed_or_rewritten(self):
        _, operation, workflow, _, origin = self.operation()
        store = operation.policy.store
        store.current.parent.mkdir(parents=True, exist_ok=True)
        store.current.write_bytes(b"{broken-index")
        prepared = workflow.prepare(origin["operation_ref"], term="public")
        self.assertEqual(prepared["gate_decision"]["decision"], "CONTINUE_DEGRADED")
        self.assertEqual(prepared["required_decisions"], [])
        self.assertEqual(store.current.read_bytes(), b"{broken-index")


if __name__ == "__main__":
    unittest.main()
