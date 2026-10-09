"""中文：恢复与最终回答的定向合同。English: state and provenance regression."""
import copy
import json
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.context_recovery_v2 import transition, classify_output, deadline_for_runtime
from cp_runtime.routing_context_contract import (runtime, validate_runtime, MODE_V2,
    CONTEXT_64K, ISOLATED_PHASES_V2)
from cp_runtime.context_semantics_v2 import expand_semantics
from cp_runtime.context_final_v2 import extract_final, read_bound_transcript, MAX_TRANSCRIPT_BYTES
from cp_runtime.routing_contract import ref


class RecoveryTests(unittest.TestCase):
    def test_research_v2_window_requires_a_frozen_wire_and_evaluation_contract(self):
        value = runtime(ROOT / "hooks/review_context_reader.py", Path(sys.executable),
                        transport_mode=MODE_V2, context_profile=CONTEXT_64K,
                        evaluation_contract=ISOLATED_PHASES_V2,
                        delivery_contract="same-call-notify/2")
        value["research_contract"] = "desktop-research-campaign/2"
        self.assertEqual(value, validate_runtime(value))
        without_wire = {key: item for key, item in value.items() if key != "delivery_contract"}
        with self.assertRaisesRegex(ValueError, "RESEARCH_V2_RUNTIME"):
            validate_runtime(without_wire)
        without_evaluation = {key: item for key, item in value.items() if key != "evaluation_contract"}
        with self.assertRaisesRegex(ValueError, "RESEARCH_V2_RUNTIME"):
            validate_runtime(without_evaluation)
        legacy = {**without_wire, "research_contract": "desktop-research-campaign/1"}
        self.assertEqual(legacy, validate_runtime(legacy))

    def test_real_epoch_milliseconds_are_supported_without_losing_integer_precision(self):
        state = transition(None, event="ATTEMPT", call_ref=ref("now"), now_ms=1790559801000)
        self.assertEqual(1790559801000, state["first_ms"])

    def test_recovery_completion_at_deadline_is_valid_but_late_completion_is_not(self):
        state = self.step(None, "ATTEMPT")
        state = self.step(state, "RETRYABLE", reason="CREATION_RECEIPT_PENDING")
        state = self.step(state, "ATTEMPT", "two", 1100)
        state = self.step(state, "READING", "two", 1200)
        self.assertEqual("DELIVERED", self.step(state, "DELIVERED", "two", 6000)["status"])
        with self.assertRaisesRegex(ValueError, "RECOVERY_DEADLINE"):
            self.step(state, "DELIVERED", "two", 6001)
        denied = self.step(state, "DENIED", "two", 6001, "CONTEXT_V2_RECOVERY_DEADLINE")
        self.assertEqual("DENIED", denied["status"])

    def test_research_v2_verified_reader_completion_after_six_seconds_is_bounded(self):
        runtime = {"research_contract": "desktop-research-campaign/2",
                   "delivery_contract": "same-call-notify/2"}
        self.assertEqual(5000, deadline_for_runtime({"research_contract": "desktop-research-campaign/1"}))
        self.assertEqual(15000, deadline_for_runtime(runtime))
        with self.assertRaisesRegex(ValueError, "RESEARCH_WINDOW_CONTRACT"):
            deadline_for_runtime({"research_contract": "desktop-research-campaign/2"})
        state = self.step(None, "ATTEMPT")
        state = self.step(state, "READING", now=1100)
        self.assertEqual("DELIVERED", self.step(state, "DELIVERED", now=7047, window=15000)["status"])
        with self.assertRaisesRegex(ValueError, "RECOVERY_DEADLINE"):
            self.step(state, "DELIVERED", now=16001, window=15000)

    def step(self, state, event, call="one", now=1000, reason="", window=5000):
        return transition(state, event=event, call_ref=ref(call), now_ms=now, reason=reason,
                          max_elapsed_ms=window)

    def test_pending_receipt_and_truncation_recover_with_history(self):
        state = self.step(None, "ATTEMPT")
        state = self.step(state, "RETRYABLE", reason="CREATION_RECEIPT_PENDING")
        state = self.step(state, "ATTEMPT", "two", 1100)
        state = self.step(state, "READING", "two", 1100)
        state = self.step(state, "RETRYABLE", "two", 1200, "OUTPUT_TRUNCATED")
        state = self.step(state, "ATTEMPT", "three", 1300)
        state = self.step(state, "READING", "three", 1300)
        state = self.step(state, "DELIVERED", "three", 1400)
        self.assertEqual("DELIVERED", state["status"])
        self.assertEqual(3, len(state["calls"]))
        self.assertEqual("CREATION_RECEIPT_PENDING", state["calls"][ref("one")]["events"]["RETRYABLE"])
        self.assertEqual("OUTPUT_TRUNCATED", state["calls"][ref("two")]["events"]["RETRYABLE"])

    def test_only_verified_retry_reason_permits_a_new_call(self):
        state = self.step(None, "ATTEMPT")
        with self.assertRaisesRegex(ValueError, "IN_PROGRESS"):
            self.step(state, "ATTEMPT", "two")
        with self.assertRaisesRegex(ValueError, "REASON_STATE"):
            self.step(state, "RETRYABLE", reason="OUTPUT_TRUNCATED")
        for reason in ("HASH_MISMATCH", "PERMISSION_DENIED", "CANCELLED", "TIMEOUT"):
            with self.assertRaises(ValueError):
                self.step(state, "RETRYABLE", reason=reason)

    def test_retries_have_attempt_deadline_and_clock_limits(self):
        state = None
        for i in range(3):
            state = self.step(state, "ATTEMPT", str(i), 1000 + i)
            state = self.step(state, "RETRYABLE", str(i), 1000 + i, "CREATION_RECEIPT_PENDING")
        with self.assertRaisesRegex(ValueError, "RETRY_LIMIT"):
            self.step(state, "ATTEMPT", "four", 1003)
        state = self.step(None, "ATTEMPT")
        state = self.step(state, "RETRYABLE", reason="CREATION_RECEIPT_PENDING")
        with self.assertRaisesRegex(ValueError, "DEADLINE"):
            self.step(state, "ATTEMPT", "two", 6001)
        with self.assertRaisesRegex(ValueError, "CLOCK_REVERSED"):
            self.step(state, "ATTEMPT", "two", 999)

    def test_duplicate_events_do_not_extend_deadline_or_reopen_call(self):
        state = self.step(None, "ATTEMPT")
        self.assertEqual(state, self.step(state, "ATTEMPT", now=4000))
        state = self.step(state, "READING")
        state = self.step(state, "DELIVERED")
        self.assertEqual(state, self.step(state, "DELIVERED", now=9000))
        with self.assertRaisesRegex(ValueError, "TERMINAL"):
            self.step(state, "ATTEMPT", "two")

    def test_hard_denial_cannot_be_retried_or_hidden_after_delivery(self):
        state = self.step(None, "DENIED", reason="BAD_COMMAND")
        with self.assertRaisesRegex(ValueError, "TERMINAL"):
            self.step(state, "ATTEMPT", "two")
        state = self.step(None, "ATTEMPT")
        state = self.step(state, "READING")
        state = self.step(state, "DELIVERED")
        state = self.step(state, "DENIED", "forbidden-extra-call", reason="BAD_COMMAND")
        self.assertEqual("DENIED", state["status"])

    def test_only_exact_success_and_strict_prefix_have_known_transport_meaning(self):
        expected = '{"context":"材料"}\n'
        self.assertEqual("DELIVERED", classify_output({"exit_code": 0, "output": expected}, expected))
        for output in ("", expected[:8]):
            self.assertEqual("OUTPUT_TRUNCATED", classify_output({"exit_code": 0, "output": output}, expected))
        for output in ({"exit_code": 1, "output": ""}, {"exit_code": False, "output": expected},
                       {"status": "success", "output": expected}, "different", None):
            self.assertEqual("DENIED", classify_output(output, expected))


class SemanticsTests(unittest.TestCase):
    def payload(self):
        return {"status": "blocking", "summary": "Verified defect", "checked_scope": ["x.py"],
                "unverified_items": [], "findings": [{"id": "F1", "dimension": "data-contract",
                "severity": "high", "evidence_level": "confirmed", "blocking": True,
                "summary": "Wrong boundary", "location": "x.py:1", "root_cause_group": "boundary",
                "required_validation": ["boundary regression"]}]}

    def test_controller_adds_only_fixed_initial_governance_values(self):
        raw = self.payload()
        result = expand_semantics(raw)
        self.assertNotIn("disposition", raw["findings"][0])
        self.assertEqual("PENDING", result["findings"][0]["disposition"])
        self.assertEqual("UNSPECIFIED", result["findings"][0]["adoption_reason"])
        self.assertFalse(result["findings"][0]["repaired"])
        self.assertEqual([], result["findings"][0]["regression_evidence"])

    def test_model_cannot_inject_governance_or_receipt(self):
        for key, value in (("repaired", True), ("disposition", "ACCEPTED")):
            payload = self.payload()
            payload["findings"][0][key] = value
            with self.assertRaises(ValueError):
                expand_semantics(payload)
        with self.assertRaises(ValueError):
            expand_semantics({**self.payload(), "context_receipt": "a" * 64})


class NativeFinalTests(unittest.TestCase):
    def test_replacement_during_open_handle_read_is_rejected(self):
        from cp_runtime import context_final_v2 as module
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.jsonl"
            path.write_bytes(self.raw())
            replacement = path.with_name("replacement.jsonl")
            replacement.write_bytes(self.raw())
            real_safe = module.safe_file
            calls = 0
            def replacing(candidate):
                nonlocal calls
                calls += 1
                if calls == 2:
                    replacement.replace(path)
                return real_safe(candidate)
            with patch.object(module, "safe_file", replacing):
                with self.assertRaises((ValueError, PermissionError)):
                    read_bound_transcript(path)

    def setUp(self):
        self.binding = dict(child_id="child", root_id="root", task_path="/root/review", role="cp_review_data_contract",
                            repo_path=str(ROOT))
        self.text = '{"status":"pass","findings":[],"summary":"审查完成","checked_scope":["x"],"unverified_items":[]}'
        self.events = [{"type": "session_meta", "payload": {"id": "child", "cwd": str(ROOT), "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": "root", "depth": 1, "agent_path": "/root/review",
                                          "agent_role": "cp_review_data_contract"}}}}},
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-1"}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer",
                "content": [{"type": "output_text", "text": self.text}]}}]

    def raw(self, events=None):
        return ("\n".join(json.dumps(e, ensure_ascii=False) for e in (events or self.events)) + "\n").encode()

    def test_exact_native_final_can_be_bound_before_task_complete_is_appended(self):
        text, proof = extract_final(self.raw(), **self.binding)
        self.assertEqual(self.text, text)
        self.assertEqual(ref("turn-1"), proof["turn_ref"])
        self.assertEqual(ref(self.events[0]), proof["header_ref"])
        self.assertEqual({"header_ref", "turn_ref", "response_ref"}, set(proof))

    def test_present_completion_must_match_same_turn_and_exact_final(self):
        self.events.append({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "turn-1",
                                                              "last_agent_message": self.text}})
        self.assertEqual(self.text, extract_final(self.raw(), **self.binding)[0])
        self.events[-1]["payload"]["last_agent_message"] += " "
        with self.assertRaisesRegex(ValueError, "COMPLETION_CONFLICT"):
            extract_final(self.raw(), **self.binding)

    def test_wrong_child_root_role_task_and_repository_are_rejected(self):
        for key in self.binding:
            with self.subTest(key=key), self.assertRaises(ValueError):
                extract_final(self.raw(), **{**self.binding, key: "foreign"})

    def test_multiple_turns_finals_and_truncated_transcripts_fail(self):
        for extra in (self.events[1], self.events[-1]):
            with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
                extract_final(self.raw(self.events + [copy.deepcopy(extra)]), **self.binding)
        for raw in (b"", self.raw()[:-1], b"x" * (MAX_TRANSCRIPT_BYTES + 1)):
            with self.assertRaisesRegex(ValueError, "BOUND"):
                extract_final(raw, **self.binding)
        self.events[-1]["payload"]["role"] = "user"
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            extract_final(self.raw(), **self.binding)


if __name__ == "__main__":
    unittest.main()
