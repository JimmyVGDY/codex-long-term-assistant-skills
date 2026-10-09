"""中文：复审者原生最终回答形成最小回执，再进入 Stop 时的交付状态。

English: Reviewer native final -> minimal receipt -> Stop-time delivery status.
"""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1, g6_handoff_v1
from cp_runtime.common import read_json
from cp_runtime.event_v2 import project_identity_for
from cp_runtime.g6_review_receipt_v1 import _delivery_path, _receipt_dir
from cp_runtime.routing_contract import ref


class G6ReviewDeliveryIntegrationTests(unittest.TestCase):
    def test_post_and_repair_reports_are_consumed_without_faking_required_checks(self):
        repo = Path(__file__).resolve().parents[1]
        hook = repo / "hooks" / "cp_hook.py"
        session = "g6-review-delivery-session"
        role = "cp_review_functional_business"
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, CODEX_HOME=home, PLUGIN_ROOT=str(repo))
            def invoke(kind, data):
                result = subprocess.run([sys.executable, "-B", str(hook), kind],
                                        input=json.dumps(data), text=True, capture_output=True,
                                        cwd=repo, env=env, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result
            root = Path(home) / "cp-assistant" / "g6-routing" / "roots" / (ref(session)[7:] + ".jsonl")
            fingerprint, project_id = project_identity_for(str(repo))
            slots = []
            for number, phase in enumerate(("post_review", "repair_review"), 1):
                message = f"Review bounded change {number}."
                item = ref({"role": role, "message_sha256": hashlib.sha256(message.encode()).hexdigest()})
                slots.append({"work_item_id": item, "allowed_profiles": ["g6-sol-medium"],
                              "baseline_profile": "g6-sol-medium", "review_phase": phase})
            g6_budget_v1.initialize(root,
                                    identity_value={"project_id": project_id,
                                                    "repo_fingerprint": fingerprint},
                                    host_session_id=session, repo_path=repo,
                                    task_id="g6-review-task", authorization_ref=ref("trusted-plan"),
                                    required_slots=slots)
            with mock.patch.dict(os.environ, CODEX_HOME=home):
                g6_handoff_v1.bind(session_id=session, repo_path=repo,
                                   new_ledger_path=root, user_change_ref=ref("trusted-plan"))
            for number, task_name in enumerate(("post_review", "repair_review"), 1):
                args = {"task_name": task_name, "agent_type": role, "model": "gpt-6-sol",
                        "reasoning_effort": "medium", "fork_turns": "none",
                        "message": f"Review bounded change {number}."}
                call = {"hook_event_name": "PreToolUse", "session_id": session,
                        "task_id": "g6-review-task", "cwd": str(repo), "tool_name": "spawn_agent",
                        "tool_use_id": f"review-call-{number}", "tool_input": args}
                self.assertEqual(invoke("PreToolUse", call).stdout.strip(), "")
                invoke("PostToolUse", {**call, "hook_event_name": "PostToolUse",
                                     "tool_response": {"task_name": "/root/" + task_name}})
                child_id = f"g6-review-child-{number}"
                transcript = Path(home) / "sessions" / "2026" / "10" / "09" / (
                    "rollout-" + child_id + ".jsonl")
                transcript.parent.mkdir(parents=True, exist_ok=True)
                report = {"status": "pass", "findings": [], "checked_scope": ["bounded fixture"],
                          "unverified_items": [], "summary": "No scoped finding"}
                events = [
                    {"type": "session_meta", "payload": {"id": child_id, "cwd": str(repo),
                     "source": {"subagent": {"thread_spawn": {"parent_thread_id": session,
                     "depth": 1, "agent_role": role, "agent_path": "/root/" + task_name}}}}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                     "phase": "final", "content": [{"type": "output_text",
                     "text": json.dumps(report)}]}},
                    {"type": "event_msg", "payload": {"type": "task_complete"}},
                ]
                transcript.write_text("".join(json.dumps(event) + "\n" for event in events),
                                      encoding="utf8")
                invoke("SubagentStop", {"hook_event_name": "SubagentStop", "session_id": session,
                       "agent_id": child_id, "agent_type": role, "cwd": str(repo),
                       "agent_transcript_path": str(transcript), "terminal_outcome": "PASS"})
            invoke("Stop", {"hook_event_name": "Stop", "session_id": session,
                            "task_id": "g6-review-task", "cwd": str(repo)})
            projected = read_json(_delivery_path(root), verify=True)
            result = projected["status"]
            self.assertEqual(result["status"], "LOCAL_RESULT_UNVERIFIED")
            self.assertTrue(result["independent_review_verified"])
            self.assertTrue(result["repair_review_verified"])
            self.assertEqual(result["review_report_statuses"]["post_review"][0]["status"], "pass")
            self.assertEqual(result["review_report_statuses"]["repair_review"][0]["status"], "pass")
            self.assertFalse(result["installed_readback_verified"])
            receipts = list(_receipt_dir(root).glob("*.json"))
            self.assertEqual(len(receipts), 2)
            self.assertTrue(all("No scoped finding" not in item.read_text(encoding="utf8")
                                for item in receipts))


if __name__ == "__main__":
    unittest.main()
