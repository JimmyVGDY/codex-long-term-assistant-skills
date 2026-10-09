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
                                        gates=[], agent_type="explorer",
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
                      "agent_role": "explorer", "agent_path": self.task_path}}}}}
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
                "agent_id": self.child, "agent_type": "explorer",
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
        self.assertEqual(response["hookSpecificOutput"]["permissionDecisionReason"],
                         "V5_CONTEXT_GUARD_FAILED")

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


if __name__ == "__main__":
    unittest.main()
