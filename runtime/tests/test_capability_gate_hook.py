"""中文：真实Hook进程验证可选流程、漏项、取消和默认兼容。

English: Real Hook processes verify opt-in lifecycle, omissions, cancellation, and defaults.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
import test_capability_gate_workflow as workflow_fixtures
from cp_runtime import capability_gate_hook as hook
from cp_runtime.capability_gate import GatePolicy, GateTask
from cp_runtime.capability_gate_workflow import GateWorkflow

ROOT = Path(__file__).resolve().parents[2]


class CapabilityGateHookTests(unittest.TestCase):
    def setUp(self):
        fixtures.CapabilityStoreTests.setUp(self)
        self.gate_root = self.base / "gate-config"
        self.policy = GatePolicy(self.store, self.gate_root)
        self.task = None
        self.flow = None
        self.env = {**os.environ, "PLUGIN_ROOT": str(ROOT), "CODEX_HOME": str(self.base / "codex"),
                    "CP_CAPABILITY_GATE_ROOT": str(self.gate_root),
                    "CP_ASSISTANT_DATA": str(self.base / "observations"),
                    "CP_DELEGATION_BUDGET_REQUIRED": "0"}
        self.env.pop("CP_DELEGATION_BUDGET_PATH", None)

    tearDown = workflow_fixtures.CapabilityGateWorkflowTests.tearDown
    choices = workflow_fixtures.CapabilityGateWorkflowTests.choices
    edit = workflow_fixtures.CapabilityGateWorkflowTests.edit

    def invoke(self, event, **values):
        data = {"hook_event_name": event, "session_id": "session", "turn_id": "turn",
                "task_id": "turn", "cwd": str(self.repo), **values}
        started = time.monotonic()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "hooks" / "cp_hook.py"), event],
            input=json.dumps(data), capture_output=True, encoding="utf-8", env=self.env, timeout=7)
        elapsed = time.monotonic() - started
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertLess(elapsed, 3 if event == "Interrupt" else 5, result.stdout)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def start(self):
        self.policy.set_enabled(True, None)
        response = self.invoke("UserPromptSubmit", prompt="PRIVATE_PROMPT_MARKER")
        self.assertIn("capability-task-prepare", response.get("hookSpecificOutput", {}).get("additionalContext", ""), response)
        self.task = GateTask(self.policy, "session", "turn")
        self.flow = GateWorkflow(self.task)
        self.assertEqual("NEW", self.task.read()["phase"])
        return response

    def test_unconfigured_and_disabled_writes_remain_neutral_without_task_state(self):
        self.assertIsNone(self.invoke("PreToolUse", tool_name="apply_patch", tool_input={"command": "PRIVATE_DIFF"}))
        self.assertEqual({}, self.invoke("Stop"))
        self.assertFalse(self.gate_root.exists())
        self.policy.set_enabled(True, None)
        self.policy.set_enabled(False, 0)
        self.assertEqual({}, self.invoke("PreToolUse", tool_name="Write"))
        self.assertEqual({}, self.invoke("Stop"))
        self.assertFalse(self.policy.state_root.exists())
        self.assertFalse(self.store.current.exists())

    def test_missing_preparation_denies_native_write_and_stop_repair_is_bounded(self):
        self.start()
        denied = self.invoke("PreToolUse", tool_name="apply_patch", tool_input={"command": "PRIVATE_DIFF"})
        self.assertEqual({"hookSpecificOutput"}, set(denied))
        self.assertEqual("deny", denied["hookSpecificOutput"]["permissionDecision"])
        first = self.invoke("Stop", stop_hook_active=False, terminal_outcome="PASS")
        self.assertEqual("block", first["decision"])
        second = self.invoke("Stop", stop_hook_active=True)
        self.assertEqual("block", second["decision"])
        final = self.invoke("Stop", stop_hook_active=True)
        self.assertFalse(final["continue"])
        self.assertEqual(2, self.task.read()["repair_count"])
        self.assertEqual("BLOCKED", self.task.read()["phase"])

    def test_prepared_edit_requires_finish_and_success_is_rechecked(self):
        self.start()
        prepared = self.flow.prepare(["app.py"], "public")
        self.assertEqual({}, self.invoke("PreToolUse", tool_name="apply_patch"))
        self.edit()
        self.assertEqual("block", self.invoke("Stop", stop_hook_active=False)["decision"])
        self.flow.finish(self.choices(prepared))
        self.assertEqual({}, self.invoke("Stop", stop_hook_active=True, terminal_outcome="PASS"))
        self.assertEqual("PASS", self.task.read()["phase"])
        (self.repo / "app.py").write_text("def public():\n    return 99\n", encoding="utf-8")
        self.assertFalse(self.invoke("Stop", stop_hook_active=True)["continue"])
        self.assertEqual("BLOCKED", self.task.read()["phase"])

    def test_new_controlled_write_invalidates_previous_pass_before_execution(self):
        self.start()
        prepared = self.flow.prepare(["app.py"], "public")
        self.edit()
        self.flow.finish(self.choices(prepared))
        self.assertEqual({}, self.invoke("PreToolUse", tool_name="Edit"))
        state = self.task.read()
        self.assertEqual("PREPARED", state["phase"])
        self.assertIsNone(state["evidence"]["finish_sha256"])
        self.assertFalse(self.flow.check()["valid"])

    def test_unprepared_external_edit_cannot_be_retroactively_approved(self):
        self.start()
        self.edit()
        self.assertFalse(self.invoke("Stop", terminal_outcome="PASS")["continue"])
        self.assertEqual("BLOCKED", self.task.read()["phase"])
        self.assertEqual(0, self.task.read()["repair_count"])

    def test_readonly_no_change_does_not_scan_or_authorize_later_write(self):
        self.start()
        response = self.invoke("Stop", last_assistant_message="PRIVATE_ANSWER_MARKER", terminal_outcome="PASS")
        self.assertIn("NO_CHANGE", response.get("systemMessage", ""), response)
        self.assertEqual("NO_CHANGE", self.task.read()["phase"])
        self.assertTrue(self.flow.check()["valid"])
        self.assertFalse(self.store.current.exists())
        self.assertEqual("deny", self.invoke("PreToolUse", tool_name="Write")["hookSpecificOutput"]["permissionDecision"])
        self.assertEqual("NEW", self.task.read()["phase"])
        for path in self.policy.state_root.rglob("*.json"):
            from cp_runtime.atomic_io import native_path
            raw = native_path(path).read_bytes()
            self.assertNotIn(b"PRIVATE_PROMPT_MARKER", raw)
            self.assertNotIn(b"PRIVATE_ANSWER_MARKER", raw)

    def test_interrupt_cancels_and_subsequent_write_and_stop_cannot_revive(self):
        self.start()
        self.assertEqual({}, self.invoke("Interrupt"))
        self.assertEqual("CANCELLED", self.task.read()["phase"])
        self.assertEqual("deny", self.invoke("PreToolUse", tool_name="Write")["hookSpecificOutput"]["permissionDecision"])
        self.assertFalse(self.invoke("Stop")["continue"])
        self.assertEqual("CANCELLED", self.task.read()["phase"])

    def test_worker_timeout_never_emits_pass_or_invalid_pretool_protocol(self):
        for event in ("UserPromptSubmit", "PreToolUse", "Stop", "Interrupt"):
            with self.subTest(event=event), patch.object(hook.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 4)):
                response = hook.supervise(ROOT, {"hook_event_name": event})
                self.assertIn("GATE_HOST_DEADLINE", json.dumps(response))
                if event == "PreToolUse":
                    self.assertEqual({"hookSpecificOutput"}, set(response))
                    self.assertEqual("deny", response["hookSpecificOutput"]["permissionDecision"])
                elif event == "Interrupt":
                    self.assertEqual({"systemMessage"}, set(response))
                else:
                    self.assertFalse(response["continue"])

    def test_corrupt_policy_and_missing_host_identity_cannot_silently_disable_gate(self):
        self.start()
        response = self.invoke("PreToolUse", tool_name="Write", turn_id="")
        self.assertEqual("deny", response["hookSpecificOutput"]["permissionDecision"])
        self.policy.path.write_bytes(b"{broken")
        self.assertFalse(self.invoke("Stop")["continue"])
        self.assertEqual("deny", self.invoke("PreToolUse", tool_name="Write")["hookSpecificOutput"]["permissionDecision"])

    def test_actual_slow_worker_is_killed_before_interrupt_host_deadline(self):
        fake = self.base / "slow-runtime"
        (fake / "hooks").mkdir(parents=True)
        marker = self.base / "late-worker-output"
        (fake / "hooks/cp_gate.py").write_text(
            "import pathlib,time\ntime.sleep(4)\npathlib.Path(" + repr(str(marker)) + ").write_text('late')\nprint('{}')\n",
            encoding="utf-8")
        started = time.monotonic()
        response = hook.supervise(fake, {"hook_event_name": "Interrupt"})
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn("GATE_HOST_DEADLINE", response["systemMessage"])
        self.assertFalse(marker.exists())

    def test_invalid_worker_schema_becomes_valid_host_specific_denial(self):
        for event, invalid in (("PreToolUse", {"continue": False}), ("Interrupt", {"decision": "block"}),
                               ("Stop", {"continue": True}), ("UserPromptSubmit", {"pass": True})):
            result = subprocess.CompletedProcess([], 0, json.dumps(invalid).encode())
            with self.subTest(event=event), patch.object(hook.subprocess, "run", return_value=result):
                response = hook.supervise(ROOT, {"hook_event_name": event})
                self.assertIn("GATE_WORKER_FAILED", json.dumps(response))
                hook.validate_response(event, response)

    def test_installed_runtime_entries_require_matching_account_binding(self):
        home = self.base / "entry-home"
        (home / "tools").mkdir(parents=True)
        for name in ("cp-runtime.py", "evolution.py"):
            (home / "tools" / name).write_text("# installed wrapper\n", encoding="utf-8")
        installed = home / "plugins/cache/cp-assistant-local/codex-cross-project-engineering-assistant/7.6.1"
        installed.mkdir(parents=True)
        state = home / "cp-assistant-v6-state.json"
        state.write_text(json.dumps({"mode": "plugin", "version": "7.6.1"}), encoding="utf-8")
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
            self.assertEqual((home / "tools/cp-runtime.py").resolve(), hook.runtime_entry(installed))
            self.assertEqual((home / "tools/evolution.py").resolve(), hook.runtime_entry(installed, "evolution.py"))
            from cp_runtime.capability_store import CapabilityError
            with self.assertRaisesRegex(CapabilityError, "GATE_RUNTIME_ENTRY_UNAVAILABLE"):
                hook.runtime_entry(installed.with_name("other-version"))
            state.write_text(json.dumps({"mode": "standalone"}), encoding="utf-8")
            self.assertEqual((home / "tools/cp-runtime.py").resolve(), hook.runtime_entry(home))
            (home / "cp-assistant-hooks").mkdir()
            (home / "cp-assistant-hooks/cp_gate.py").write_text("print('{}')\n", encoding="utf-8")
            self.assertEqual({}, hook.supervise(home, {"hook_event_name": "Stop"}))


if __name__ == "__main__":
    unittest.main()
