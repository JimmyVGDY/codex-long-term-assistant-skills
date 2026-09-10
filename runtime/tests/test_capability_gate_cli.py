"""中文：真实CLI进程验证启用、准备、完成、降级和旧查询兼容。

English: Real CLI processes verify opt-in, preparation, completion, partial coverage, and legacy queries.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
import test_capability_gate_workflow as workflow_fixtures
from cp_runtime.capability_gate import GatePolicy, GateTask
from cp_runtime.capability_gate_workflow import GateWorkflow
from cp_runtime.capability_operation import CapabilityOperation
from cp_runtime.patch_intent import parse_apply_patch

ENTRY = Path(__file__).resolve().parents[2] / "scripts" / "cp-runtime.py"


class CapabilityGateCLITests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = workflow_fixtures.CapabilityGateWorkflowTests.tearDown

    def cli(self, action, *args, expected=0):
        command = [sys.executable, str(ENTRY), action, "--profile", str(self.profile), "--repo-path", str(self.repo)]
        if action.startswith(("capability-gate-", "capability-task-")):
            command.extend(["--gate-root", str(self.base / "gate-config")])
        if action.startswith("capability-task-"):
            command.extend(["--session-id", "session", "--turn-id", "turn"])
        result = subprocess.run([*command, *args], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(expected, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else result.stderr

    def host_start(self):
        self.cli("capability-gate-enable")
        self.flow = GateWorkflow(GateTask(GatePolicy(self.store, self.base / "gate-config"), "session", "turn"))
        self.flow.begin()

    def operation_cli(self, action, operation_ref, *args, expected=0):
        command = [sys.executable, str(ENTRY), action, "--profile", str(self.profile),
                   "--repo-path", str(self.repo), "--gate-root", str(self.base / "gate-config"),
                   "--operation-ref", operation_ref, *args]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(expected, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else result.stderr

    def test_optional_policy_commands_preserve_profile_and_do_not_create_index(self):
        original = self.profile.read_bytes()
        self.assertFalse(self.cli("capability-gate-status")["configured"])
        self.assertFalse((self.base / "gate-config").exists())
        self.assertTrue(self.cli("capability-gate-enable")["policy"]["enabled"])
        self.assertTrue(self.cli("capability-gate-status")["enabled"])
        self.cli("capability-gate-disable", "--expected-revision", "0")
        self.assertFalse(self.cli("capability-gate-status")["enabled"])
        self.assertEqual(original, self.profile.read_bytes())
        self.assertFalse(self.store.current.exists())

    def test_prepare_requires_host_origin_and_cli_cannot_create_it(self):
        self.cli("capability-gate-enable")
        result = self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public", expected=1)
        self.assertIn("GATE_TASK_MISSING", result)
        result = self.cli("capability-task-begin", expected=2)
        self.assertIn("invalid choice", result)

    def test_operation_v2_cli_consumes_hook_origin_without_legacy_task(self):
        self.policy = GatePolicy(self.store, self.base / "gate-config")
        self.policy.set_enabled(True, None)
        operation = CapabilityOperation(self.policy, "session", "turn")
        command = ("*** Begin Patch\n*** Update File: app.py\n@@\n"
                   "-    return 1\n+    return 2\n*** End Patch\n")
        intent = parse_apply_patch(command, self.repo)
        origin = operation.create_or_replay_origin(
            "attempt-a", intent, intent["target_paths"], intent,
        )
        ref = origin["operation_ref"]
        prepared = self.operation_cli("capability-task-prepare", ref, "--term", "public")
        self.assertEqual("READY", prepared["state"]["state"])
        self.assertFalse(self.policy.state_root.exists())
        operation.find_and_claim(tool_use_id="attempt-b", intent=intent,
                                 targets=intent["target_paths"], prestate=intent)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        operation.record_posttool(ref, "attempt-b", {"ok": True}, summary_code="RECEIVED")
        decisions = self.base / "operation-decisions.json"
        decisions.write_text(json.dumps([
            {"id": item["id"], "choice": "extend", "reason": "保持公开入口兼容"}
            for item in prepared["required_decisions"]
        ]), encoding="utf-8")
        finished = self.operation_cli("capability-task-finish", ref, "--decisions", str(decisions))
        self.assertEqual("VERIFIED", finished["state"]["state"])
        self.assertTrue(self.operation_cli("capability-task-check", ref)["valid"])

    def test_real_prepare_finish_check_updates_index_and_checks_all_decisions(self):
        self.host_start()
        prepared = self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public")
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        self.assertIn("GATE_DECISIONS_MISSING", self.cli("capability-task-finish", expected=1))
        decisions = self.base / "decisions.json"
        decisions.write_text(json.dumps([{"id": c["id"], "choice": "extend", "reason": "Existing public entry remains compatible"}
                                         for c in prepared["required_decisions"]]), encoding="utf-8")
        self.assertEqual("PASS", self.cli("capability-task-finish", "--decisions", str(decisions))["state"]["phase"])
        self.assertTrue(self.cli("capability-task-check")["valid"])
        self.cli("capability-task-cancel")
        self.assertEqual("CANCELLED", self.cli("capability-task-check")["state"]["phase"])

    def test_oversized_context_is_persisted_as_partial_without_auto_repair(self):
        (self.repo / "package-lock.json").write_text("x" * (128 * 1024 + 1), encoding="utf-8")
        fixtures.git(self.repo, "add", ".")
        fixtures.git(self.repo, "commit", "-qm", "large lock")
        self.host_start()
        result = self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public", expected=1)
        self.assertEqual("PARTIAL", result["state"]["phase"])
        self.assertFalse(self.cli("capability-task-check")["valid"])
        self.assertEqual("HALT", self.flow.task.request_repair(False, ["NEEDS_PREPARE"])["action"])

    def test_preparation_after_edit_is_persisted_as_blocked(self):
        self.host_start()
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        result = self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public", expected=1)
        self.assertEqual("BLOCKED", result["state"]["phase"])
        self.assertFalse(self.store.current.exists())

    def test_local_exception_needs_reason_and_no_change_is_distinct_from_pass(self):
        self.host_start()
        result = self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public",
                          "--local-only-reason", "", expected=1)
        self.assertIn("CLASSIFICATION_MISSING", result)
        self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public",
                 "--local-only-reason", "Source check confirms only local implementation is involved")
        self.assertEqual("NO_CHANGE", self.cli("capability-task-finish")["state"]["phase"])
        self.assertFalse(self.store.current.exists())

    def test_legacy_query_does_not_write_gate_state_or_index(self):
        self.host_start()
        self.cli("capability-task-prepare", "--scope", "app.py", "--term", "public")
        original = (self.flow.task.path.read_bytes(), self.store.current.read_bytes())
        result = self.cli("capability-query", "--term", "public")
        self.assertEqual("OK", result["status"])
        self.assertEqual(original, (self.flow.task.path.read_bytes(), self.store.current.read_bytes()))


if __name__ == "__main__":
    unittest.main()
