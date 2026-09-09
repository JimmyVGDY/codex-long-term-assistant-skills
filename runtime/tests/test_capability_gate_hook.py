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
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
import test_capability_gate_workflow as workflow_fixtures
from cp_runtime import capability_gate_hook as hook
from cp_runtime.capability_gate import GatePolicy

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

    def legacy_task(self, phase):
        policy = self.policy.read() if self.policy.path.exists() else None
        self.policy.set_enabled(True, None if policy is None else policy["revision"])
        session_id = "legacy-session-" + phase
        turn_id = "legacy-turn-" + phase
        state_path = self.policy.state_root / (phase.lower() + ".json")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"phase": phase, "legacy": True}, sort_keys=True), encoding="utf-8")
        return SimpleNamespace(session_id=session_id, turn_id=turn_id, path=state_path)

    @staticmethod
    def legacy_snapshot(task):
        return task.path.read_bytes()

    def invoke_legacy(self, task, event, **values):
        return self.invoke(event, session_id=task.session_id, turn_id=task.turn_id,
                           task_id=task.turn_id, **values)

    def handle_legacy(self, task, event, **values):
        with patch.dict(os.environ, {"CP_CAPABILITY_GATE_ROOT": str(self.gate_root)}):
            return hook.handle(ROOT, {"hook_event_name": event, "cwd": str(self.repo),
                                      "session_id": task.session_id, "turn_id": task.turn_id,
                                      "task_id": task.turn_id, **values})["response"]

    def test_unconfigured_and_disabled_native_writes_remain_neutral_without_task_state(self):
        self.assertIsNone(self.invoke("PreToolUse", tool_name="apply_patch", tool_input={"command": "PRIVATE_DIFF"}))
        self.assertEqual({}, self.invoke("Stop"))
        self.assertFalse(self.gate_root.exists())
        self.policy.set_enabled(True, None)
        self.policy.set_enabled(False, 0)
        self.assertIsNone(self.invoke("PreToolUse", tool_name="Write"))
        self.assertEqual({}, self.invoke("Stop"))
        self.assertFalse(self.policy.state_root.exists())
        self.assertFalse(self.store.current.exists())

    def test_user_prompt_submission_is_observation_only_without_gate_task_or_context_injection(self):
        self.policy.set_enabled(True, None)
        response = self.invoke("UserPromptSubmit", prompt="PRIVATE_PROMPT_MARKER")
        self.assertIsNone(response)
        self.assertFalse(self.policy.state_root.exists())
        observed = list((self.base / "observations").rglob("task-outcome-v3.jsonl"))
        self.assertEqual(1, len(observed))
        raw = observed[0].read_bytes()
        self.assertIn(b"TURN_OPENED", raw)
        self.assertNotIn(b"PRIVATE_PROMPT_MARKER", raw)
        with patch.object(hook, "locate_policy", side_effect=AssertionError("policy lookup is forbidden")):
            result = hook.handle(ROOT, {"hook_event_name": "UserPromptSubmit", "cwd": str(self.repo)})
        self.assertEqual({}, result["response"])
        self.assertTrue(result["observe"])

    def test_legacy_native_writes_never_reuse_prepared_or_pass_states(self):
        for phase in ("PREPARED", "PASS", "REPAIR_REQUESTED", "CANCELLED"):
            with self.subTest(phase=phase):
                task = self.legacy_task(phase)
                before = self.legacy_snapshot(task)
                for tool_name in ("apply_patch", "Edit", "Write"):
                    denied = self.handle_legacy(task, "PreToolUse", tool_name=tool_name)
                    self.assertEqual("deny", denied["hookSpecificOutput"]["permissionDecision"])
                    self.assertIn("LEGACY_WRITE_ORIGIN_UNAVAILABLE",
                                  denied["hookSpecificOutput"]["permissionDecisionReason"])
                self.assertEqual(before, self.legacy_snapshot(task))

    def test_stop_is_neutral_and_never_changes_any_legacy_state(self):
        for phase in ("PREPARED", "PASS", "REPAIR_REQUESTED", "CANCELLED"):
            with self.subTest(phase=phase):
                task = self.legacy_task(phase)
                before = self.legacy_snapshot(task)
                response = self.handle_legacy(task, "Stop", stop_hook_active=True, terminal_outcome="PASS")
                self.assertEqual({}, response)
                self.assertEqual(before, self.legacy_snapshot(task))

    def test_interrupt_keeps_host_control_and_never_changes_legacy_state(self):
        task = self.legacy_task("PREPARED")
        before = self.legacy_snapshot(task)
        self.assertIsNone(self.invoke_legacy(task, "Interrupt"))
        self.assertEqual(before, self.legacy_snapshot(task))
        self.assertEqual({}, hook.failure_response("Stop", "GATE_WORKER_FAILED"))
        self.assertEqual({}, hook.failure_response("UserPromptSubmit", "GATE_WORKER_FAILED"))
        self.assertEqual({"systemMessage"}, set(hook.failure_response("Interrupt", "GATE_WORKER_FAILED")))

    def test_concurrent_and_sequential_legacy_writes_never_allow(self):
        task = self.legacy_task("PASS")
        before = self.legacy_snapshot(task)
        tools = ["apply_patch", "Edit", "Write"] * 3
        with ThreadPoolExecutor(max_workers=3) as executor:
            responses = list(executor.map(lambda name: self.handle_legacy(task, "PreToolUse", tool_name=name), tools))
        for response in responses:
            self.assertEqual("deny", response["hookSpecificOutput"]["permissionDecision"])
            self.assertNotIn("allow", json.dumps(response).lower())
        self.assertEqual(before, self.legacy_snapshot(task))

    def test_worker_timeout_never_emits_pass_or_invalid_pretool_protocol(self):
        for event in ("UserPromptSubmit", "PreToolUse", "Stop", "Interrupt"):
            with self.subTest(event=event), patch.object(hook.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 4)):
                response = hook.supervise(ROOT, {"hook_event_name": event})
                if event == "PreToolUse":
                    self.assertEqual({"hookSpecificOutput"}, set(response))
                    self.assertEqual("deny", response["hookSpecificOutput"]["permissionDecision"])
                    self.assertIn("GATE_HOST_DEADLINE", json.dumps(response))
                elif event == "Interrupt":
                    self.assertEqual({"systemMessage"}, set(response))
                    self.assertIn("GATE_HOST_DEADLINE", json.dumps(response))
                else:
                    self.assertEqual({}, response)

    def test_corrupt_policy_and_missing_host_identity_cannot_permit_legacy_writes(self):
        self.policy.set_enabled(True, None)
        response = self.invoke("PreToolUse", tool_name="Write", turn_id="")
        self.assertEqual("deny", response["hookSpecificOutput"]["permissionDecision"])
        self.policy.path.write_bytes(b"{broken")
        self.assertEqual({}, self.invoke("Stop"))
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

    def test_invalid_worker_schema_becomes_event_legal_response(self):
        for event, invalid in (("PreToolUse", {"continue": False}), ("Interrupt", {"decision": "block"}),
                               ("Stop", {"continue": True}), ("UserPromptSubmit", {"hookSpecificOutput": {}})):
            result = subprocess.CompletedProcess([], 0, json.dumps(invalid).encode())
            with self.subTest(event=event), patch.object(hook.subprocess, "run", return_value=result):
                response = hook.supervise(ROOT, {"hook_event_name": event})
                if event in {"PreToolUse", "Interrupt"}:
                    self.assertIn("GATE_WORKER_FAILED", json.dumps(response))
                else:
                    self.assertEqual({}, response)
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
