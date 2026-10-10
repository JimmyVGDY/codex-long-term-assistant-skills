"""中文：续跑保留根预算、旧费用和原生回合边界。

English: Continuations preserve the root budget, old charges and native turns.
"""
import json
import unittest

from cp_runtime import g6_budget_v1
from cp_runtime.common import utc_now
from tests import test_g6_native_context_stop_regression as fixtures


class NativeContinuationTests(unittest.TestCase):
    setUp = fixtures.G6NativeContextStopRegressionTests.setUp
    event = fixtures.G6NativeContextStopRegressionTests.event
    run_hook = fixtures.G6NativeContextStopRegressionTests.run_hook

    def continuation_event(self, event="PreToolUse"):
        data = self.event(event)
        data.pop("agent_id")
        data.pop("agent_type")
        data.update(tool_name="followup_task", tool_use_id="follow-call-1",
                    tool_input={"target": self.task_path, "message": "Read the updated material."})
        return data

    def test_running_child_routes_to_non_starting_message_without_reservation(self):
        before = g6_budget_v1.read_budget(self.root)
        result = self.run_hook("cp_hook.py", self.continuation_event())
        self.assertIn("reroute_original_message", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(g6_budget_v1.read_budget(self.root)["reservations"], before["reservations"])

    def test_idle_child_continuation_charges_new_attempt_in_same_root(self):
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        before = g6_budget_v1.read_budget(self.root)
        self.assertEqual(self.run_hook("cp_hook.py", self.continuation_event()), {})
        reserved = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(reserved["reservations"]), 2)
        self.assertEqual(reserved["root"], before["root"])
        post = self.continuation_event("PostToolUse")
        post["tool_response"] = {"task_name": self.task_path}
        self.assertEqual(self.run_hook("cp_hook.py", post), {})
        # 中文：旧回合的迟到 Stop 不能结算新续跑。
        # English: A late Stop from the previous turn cannot settle this reentry.
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        self.assertEqual(len(g6_budget_v1.read_budget(self.root)["terminals"]), 1)
        stamp = utc_now()
        started = {"timestamp": stamp, "type": "event_msg", "payload": {
            "type": "task_started", "turn_id": "continuation-turn"}}
        final = {"timestamp": stamp, "type": "response_item", "payload": {
            "type": "message", "role": "assistant", "phase": "final_answer",
            "content": [{"type": "output_text", "text": "Updated material read."}]}}
        with self.transcript.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(started) + "\n" + json.dumps(final) + "\n")
        stop = self.event("SubagentStop")
        stop["turn_id"] = "continuation-turn"
        self.run_hook("cp_hook.py", stop)
        ended = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(ended["terminals"]), 2)
        usage = g6_budget_v1.snapshot(ended, work_item_id="other", depth=0)
        self.assertEqual(usage["completed_charged_units"], 8)
        self.assertEqual(usage["active_calls"], 0)
        self.run_hook("cp_hook.py", stop)
        self.assertEqual(g6_budget_v1.read_budget(self.root)["sequence"], ended["sequence"])
        if self.role.startswith("cp_review_"):
            from cp_runtime.g6_review_receipt_v1 import _receipt_dir
            self.assertEqual(len(list(_receipt_dir(self.root).glob("*.json"))), 2)

    def test_native_new_turn_recovers_ambiguous_continuation_response(self):
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        self.assertEqual(self.run_hook("cp_hook.py", self.continuation_event()), {})
        stamp = utc_now()
        record = {"timestamp": stamp, "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "recovered-turn"}}
        with self.transcript.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(record) + "\n")
        stop = self.event("SubagentStop")
        stop["turn_id"] = "recovered-turn"
        self.run_hook("cp_hook.py", stop)
        state = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(state["receipts"]), 2)
        self.assertEqual(len(state["terminals"]), 2)
        self.assertEqual(len(state["reservations"]), 2)

    def test_unbound_late_completion_cannot_settle_continuation(self):
        self.run_hook("cp_hook.py", self.event("SubagentStop"))
        self.run_hook("cp_hook.py", self.continuation_event())
        post = self.continuation_event("PostToolUse")
        post["tool_response"] = {"task_name": self.task_path}
        self.run_hook("cp_hook.py", post)
        stamp = utc_now()
        filler = {"timestamp": stamp, "type": "event_msg", "payload": {
            "type": "fixture_data", "text": "x" * 2_100_000}}
        late = {"timestamp": stamp, "type": "event_msg", "payload": {"type": "task_complete"}}
        with self.transcript.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(filler) + "\n" + json.dumps(late) + "\n")
        stop = self.event("SubagentStop")
        stop.update(turn_id="new-turn", terminal_outcome="PASS")
        self.run_hook("cp_hook.py", stop)
        pending = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(pending["terminals"]), 1)
        self.assertEqual(g6_budget_v1.snapshot(pending, work_item_id="other", depth=0)["active_calls"], 1)
        late["payload"]["turn_id"] = "new-turn"
        with self.transcript.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(late) + "\n")
        self.run_hook("cp_hook.py", stop)
        ended = g6_budget_v1.read_budget(self.root)
        self.assertEqual(len(ended["terminals"]), 2)
        self.assertEqual(g6_budget_v1.snapshot(ended, work_item_id="other", depth=0)["active_calls"], 0)


class NativeReviewerContinuationTests(NativeContinuationTests):
    agent_role = "cp_review_security_access"


if __name__ == "__main__":
    unittest.main()
