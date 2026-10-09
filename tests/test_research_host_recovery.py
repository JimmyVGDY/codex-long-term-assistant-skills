"""中文：宿主容量证明必须绑定一个终态回合，不能绑定模型回答。

English: The host capacity proof must bind one terminal turn, never a model answer.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.research_host_recovery import _terminal_capacity_error, ERROR_CODE, ERROR_MESSAGE


class HostCapacityTerminalTests(unittest.TestCase):
    def events(self):
        return [
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn_one"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user"}},
            {"type": "turn_context", "payload": {"turn_id": "turn_one", "model": "gpt-5.6-terra", "effort": "medium"}},
            {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "turn_one",
                                                "last_agent_message": None,
                                                "error": {"message": ERROR_MESSAGE, "codex_error_info": ERROR_CODE}}},
        ]

    def check(self, events):
        return _terminal_capacity_error(events, model="gpt-5.6-terra", effort="medium")

    def test_one_exact_capacity_failure_has_no_model_verdict(self):
        context, terminal = self.check(self.events())
        self.assertEqual("turn_one", context["payload"]["turn_id"])
        self.assertEqual(ERROR_CODE, terminal["payload"]["error"]["codex_error_info"])

    def test_wrong_or_resumed_turn_and_nonterminal_trail_are_denied(self):
        original = self.events()
        cases = []
        second_start = copy.deepcopy(original)
        second_start.insert(-1, {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn_two"}})
        cases.append(second_start)
        wrong_complete = copy.deepcopy(original)
        wrong_complete[-1]["payload"]["turn_id"] = "turn_two"
        cases.append(wrong_complete)
        resumed_user = copy.deepcopy(original)
        resumed_user.insert(-1, {"type": "response_item", "payload": {"type": "message", "role": "user"}})
        cases.append(resumed_user)
        trailing_event = copy.deepcopy(original)
        trailing_event.append({"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn_two"}})
        cases.append(trailing_event)
        wrong_model = copy.deepcopy(original)
        wrong_model[2]["payload"]["model"] = "gpt-6-luna"
        cases.append(wrong_model)
        missing_turn = copy.deepcopy(original)
        for position in (0, 2, 3):
            missing_turn[position]["payload"].pop("turn_id")
        cases.append(missing_turn)
        empty_turn = copy.deepcopy(original)
        for position in (0, 2, 3):
            empty_turn[position]["payload"]["turn_id"] = ""
        cases.append(empty_turn)
        out_of_order = copy.deepcopy(original)
        out_of_order[1], out_of_order[2] = out_of_order[2], out_of_order[1]
        cases.append(out_of_order)
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ValueError):
                self.check(events)

    def test_forged_error_or_model_work_is_denied(self):
        original = self.events()
        cases = []
        wrong_error = copy.deepcopy(original)
        wrong_error[-1]["payload"]["error"]["codex_error_info"] = "rate_limited"
        cases.append(wrong_error)
        with_final = copy.deepcopy(original)
        with_final.insert(-1, {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer"}})
        cases.append(with_final)
        with_tool = copy.deepcopy(original)
        with_tool.insert(-1, {"type": "response_item", "payload": {"type": "custom_tool_call"}})
        cases.append(with_tool)
        unknown_call = copy.deepcopy(original)
        unknown_call.insert(-1, {"type": "response_item", "payload": {"type": "future_tool_invocation"}})
        cases.append(unknown_call)
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ValueError):
                self.check(events)


if __name__ == "__main__":
    unittest.main()
