"""中文：采用真实 Desktop Hook 字段形状，验证新子任务与旧研究头并存。

English: Realistic Desktop Hook shape: a new child coexists with an old research head.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1, g6_handoff_v1, research_campaign
from cp_runtime.routing_contract import ref
from tests.test_g6_budget_v1 import capability, facts


class G6NativeContextStopRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex-home"
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.package = Path(__file__).resolve().parents[1]
        self.session = "native-parent-session"
        self.child = "01a1203e-51f7-73f2-aa8c-2dcdf97944d1"
        self.task_path = "/root/g6_native_verify_01"
        self.role = getattr(self, "agent_role", "explorer")
        self.root = self.home / "cp-assistant" / "g6-routing" / "roots" / (
            ref(self.session)[7:] + ".jsonl")
        g6_budget_v1.initialize(self.root, identity_value=facts()["identity"],
                                host_session_id=self.session, repo_path=self.repo,
                                task_id="task-a", authorization_ref=ref("native-test-authority"))
        with mock.patch.dict(os.environ, CODEX_HOME=str(self.home)):
            g6_handoff_v1.bind(session_id=self.session, repo_path=self.repo,
                               new_ledger_path=self.root,
                               user_change_ref=ref("policy-handoff"))
            # 中文：真实聊天里旧 V5 研究头与新 G6 绑定同时存在；旧路由不能占用该新子任务。
            # English: A retained V5 research head coexists with a new G6 binding in the
            # real chat.  The legacy router must not claim this new child.
            old_head = research_campaign._head(self.session)
            old_head.parent.mkdir(parents=True, exist_ok=True)
            old_head.write_text('{"schema_version":"research-session-head/1"}\n', encoding="utf8")
        prepared = g6_budget_v1.prepare(self.root, facts=facts(), capability=capability(),
                                        gates=[], agent_type=self.role,
                                        task_name="g6_native_verify_01",
                                        message="Read only installed metadata.",
                                        decision_time="2026-10-09T10:38:00Z")
        g6_budget_v1.approve_and_reserve(
            self.root, permit_id=prepared["permit_id"], host_call_id="native-call-1",
            session_id=self.session, cwd=self.repo,
            args=prepared["decision"]["exact_tool_parameters"], now="2026-10-09T10:38:37Z")
        g6_budget_v1.record_receipt(self.root, host_call_id="native-call-1",
                                    disposition="created", agent_path=self.task_path,
                                    proof_ref=ref("native-created"))
        self.transcript = self.home / "sessions" / "2026" / "10" / "09" / (
            "rollout-2026-10-09T18-38-37-" + self.child + ".jsonl")
        self.transcript.parent.mkdir(parents=True)
        header = {"type": "session_meta", "payload": {"id": self.child,
                  "cwd": str(self.repo), "source": {"subagent": {"thread_spawn": {
                      "parent_thread_id": self.session, "depth": 1,
                      "agent_role": self.role, "agent_path": self.task_path}}}}}
        # 中文：原生 SubagentStop 可在 final_answer 之后、task_complete 尚未追加到转录之前到达。
        # English: Native SubagentStop can arrive after final_answer but before the
        # subsequent task_complete event is appended to the transcript.
        final = {"type": "response_item", "payload": {"type": "message",
                 "role": "assistant", "phase": "final_answer",
                 "content": [{"type": "output_text", "text": "Read-only task incomplete."}]}}
        self.transcript.write_text(json.dumps(header) + "\n" + json.dumps(final) + "\n",
                                   encoding="utf8")
        self.env = dict(os.environ, CODEX_HOME=str(self.home), PLUGIN_ROOT=str(self.package))

    def event(self, hook_name="PreToolUse"):
        return {"hook_event_name": hook_name, "session_id": self.session,
                "turn_id": "native-child-turn", "task_id": "native-child-turn",
                "agent_id": self.child, "agent_type": self.role,
                "permission_mode": "default", "cwd": str(self.repo),
                "transcript_path": str(self.transcript),
                "agent_transcript_path": str(self.transcript),
                "tool_name": "exec_command", "tool_use_id": "native-read-call",
                "tool_input": {"cmd": "Get-Content -LiteralPath C:/installed-state.json -Raw"},
                "terminal_outcome": "UNKNOWN", "stop_hook_active": False}

    def run_hook(self, filename, event):
        result = subprocess.run([sys.executable, "-B", str(self.package / "hooks" / filename),
                                 event["hook_event_name"]], input=json.dumps(event),
                                text=True, capture_output=True, cwd=self.repo,
                                env=self.env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_new_child_context_hook_uses_g6_owner_before_old_v5_head(self):
        before = g6_budget_v1.read_budget(self.root)["head_hash"]
        response = self.run_hook("cp_context.py", self.event())
        self.assertEqual(response, {})
        self.assertEqual(g6_budget_v1.read_budget(self.root)["head_hash"], before)

    def test_old_research_child_without_g6_binding_keeps_v5_guard(self):
        pointer = g6_handoff_v1.pointer_for(
            self.session, directory=self.home / "cp-assistant" / "g6-routing")
        pointer.unlink()
        response = self.run_hook("cp_context.py", self.event())
        self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("V5_CONTEXT_GUARD_FAILED",
                      response["hookSpecificOutput"]["permissionDecisionReason"])

    def test_parent_read_does_not_open_unavailable_child_budget(self):
        self.root.write_bytes(b"{damaged-test-ledger")
        parent = self.event()
        parent.pop("agent_id")
        parent.pop("agent_type")
        self.assertEqual(self.run_hook("cp_context.py", parent), {})

    def test_dispatch_still_rejects_corrupt_budget_in_its_own_guard(self):
        self.root.write_bytes(b"{damaged-test-ledger")
        parent = self.event()
        parent.pop("agent_id")
        parent.pop("agent_type")
        parent.update(tool_name="spawn_agent", tool_input={"task_name": "other"})
        process = subprocess.run(
            [sys.executable, "-B", str(self.package / "hooks/cp_hook.py"), "PreToolUse"],
            input=json.dumps(parent), text=True, encoding="utf-8", capture_output=True, cwd=self.repo,
            env=self.env, timeout=30)
        response = json.loads(process.stdout)
        self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_subagent_stop_with_final_answer_before_task_complete_charges_once(self):
        stop = self.event("SubagentStop")
        self.run_hook("cp_hook.py", stop)
        state = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(state["terminals"]), 1)
        terminal = next(iter(state["terminals"].values()))
        self.assertEqual(terminal["outcome"], "UNKNOWN")
        self.assertEqual(g6_budget_v1.snapshot(state, work_item_id="other", depth=0)
                         ["completed_charged_units"], 4)
        self.run_hook("cp_hook.py", stop)
        self.assertEqual(len(g6_budget_v1.read_budget(self.root)["terminals"]), 1)

    def test_large_native_transcript_does_not_leave_finished_child_inflight(self):
        header, final = self.transcript.read_text(encoding="utf8").splitlines()
        filler = json.dumps({"type": "event_msg", "payload": {
            "type": "fixture_data", "text": "x" * 2_100_000}})
        self.transcript.write_text(header + "\n" + filler + "\n" + final + "\n", encoding="utf8")
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        state = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(state["terminals"]), 1)
        self.assertEqual(g6_budget_v1.snapshot(state, work_item_id="other", depth=0)["active_calls"], 0)

    def test_partial_append_keeps_complete_native_final_available(self):
        with self.transcript.open("ab") as stream:
            stream.write(b'{"type":"event_msg","payload":')
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        state = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(state["terminals"]), 1)
        self.assertEqual(next(iter(state["terminals"].values()))["outcome"], "UNKNOWN")

    def test_late_final_is_reconciled_on_parent_stop_without_new_call(self):
        original = self.transcript.read_text(encoding="utf8")
        header = original.splitlines()[0]
        self.transcript.write_text(header + "\n", encoding="utf8")
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        before = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(before["terminals"]), 0)
        self.transcript.write_text(original, encoding="utf8")
        parent = self.event("Stop")
        parent.pop("agent_id")
        parent.pop("agent_type")
        self.run_hook("cp_hook.py", parent)
        after = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(after["terminals"]), 1)
        self.assertEqual(after["reservations"], before["reservations"])
        self.run_hook("cp_hook.py", parent)
        self.assertEqual(g6_budget_v1.read_budget(self.root)["sequence"], after["sequence"])

    def test_previous_turn_terminal_cannot_finish_current_turn(self):
        header = self.transcript.read_text(encoding="utf8").splitlines()[0]
        stale = json.dumps({"type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "previous-turn"}})
        self.transcript.write_text(header + "\n" + stale + "\n", encoding="utf8")
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        self.assertEqual(len(g6_budget_v1.read_budget(self.root)["terminals"]), 0)

    def test_native_agent_id_is_resolved_only_inside_its_bound_root(self):
        self.run_hook("cp_hook.py", self.event("SubagentStart"))
        parent = self.event()
        parent.pop("agent_id")
        parent.pop("agent_type")
        parent.update(tool_name="send_message", tool_input={"target": self.child, "message": "Report status."})
        self.assertEqual(self.run_hook("cp_hook.py", parent), {})
        parent["tool_input"]["target"] = "01a12381-f66d-7261-914f-000000000000"
        result = self.run_hook("cp_hook.py", parent)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_native_child_header_recovers_missing_parent_creation_receipt(self):
        lines = self.root.read_bytes().splitlines(keepends=True)
        self.assertEqual(json.loads(lines[-1])["event_type"], "HOST_RECEIPT")
        self.root.write_bytes(b"".join(lines[:-1]))
        self.run_hook("cp_hook.py", self.event("SubagentStart"))
        created = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(created["receipts"]), 1)
        self.assertEqual(len(created["reservations"]), 1)
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        ended = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(ended["terminals"]), 1)

    def test_corrupt_auxiliary_record_does_not_starve_valid_reconciliation(self):
        original = self.transcript.read_text(encoding="utf8")
        self.transcript.write_text(original.splitlines()[0] + "\n", encoding="utf8")
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        directory = self.root.with_name(self.root.name + ".reconciliation")
        (directory / "!corrupt.json").write_bytes(b"{broken")
        self.transcript.write_text(original, encoding="utf8")
        parent = self.event("Stop")
        parent.pop("agent_id")
        parent.pop("agent_type")
        self.run_hook("cp_hook.py", parent)
        self.assertEqual(len(g6_budget_v1.read_budget(self.root)["terminals"]), 1)
        self.assertEqual((directory / "!corrupt.json").read_bytes(), b"{broken")


if __name__ == "__main__":
    unittest.main()
