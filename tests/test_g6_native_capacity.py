"""中文：桌面入口消费已授权根额度，不扩容或重置历史。

English: Desktop admission consumes authorized root capacity without expansion.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1, g6_handoff_v1
from cp_runtime.routing_contract import ref
from tests.test_g6_budget_v1 import facts


class NativeCapacityTests(unittest.TestCase):
    def test_all_templates_use_real_hook_and_preserve_capacity(self):
        package = Path(__file__).resolve().parents[1]
        for capacity, units in [("LIGHT", 4), ("STANDARD", 16), ("STRICT", 32)]:
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                repo, home = base / "repo", base / "home"
                repo.mkdir()
                ledger = home / "budget.jsonl"
                session = "native-capacity-" + capacity.lower()
                g6_budget_v1.initialize(ledger, identity_value=facts()["identity"],
                    host_session_id=session, repo_path=repo, task_id="capacity",
                    authorization_ref=ref("authorized-" + capacity), capacity_class=capacity)
                with mock.patch.dict(os.environ, CODEX_HOME=str(home)):
                    g6_handoff_v1.bind(session_id=session, repo_path=repo,
                        new_ledger_path=ledger, user_change_ref=ref("authorized-capacity"))
                env = dict(os.environ, CODEX_HOME=str(home), PLUGIN_ROOT=str(package), PYTHONUTF8="1")
                event = {"hook_event_name": "PreToolUse", "session_id": session,
                         "turn_id": "turn", "cwd": str(repo), "tool_name": "spawn_agent",
                         "tool_use_id": "call-one", "tool_input": {
                             "task_name": "capacity_one", "agent_type": "explorer",
                             "model": "gpt-6-sol", "reasoning_effort": "medium",
                             "fork_turns": "none", "message": "Read the bounded task."}}
                def invoke(payload):
                    result = subprocess.run([sys.executable, "-B", str(package / "hooks/cp_hook.py"),
                                             "PreToolUse"], input=json.dumps(payload),
                                            text=True, encoding="utf-8", capture_output=True,
                                            cwd=repo, env=env, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout.strip()
                self.assertEqual(invoke(event), "")
                state = g6_budget_v1.read_budget(ledger)
                self.assertEqual(state["root"]["capacity_class"], capacity)
                self.assertEqual(g6_budget_v1.snapshot(state, work_item_id="other", depth=0)["capacity_units"], units)
                self.assertEqual(len(state["reservations"]), 1)
                if capacity == "LIGHT":
                    event["tool_use_id"] = "call-two"
                    event["tool_input"]["task_name"] = "capacity_two"
                    denied = json.loads(invoke(event))
                    self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
                    self.assertEqual(len(g6_budget_v1.read_budget(ledger)["reservations"]), 1)


if __name__ == "__main__":
    unittest.main()
