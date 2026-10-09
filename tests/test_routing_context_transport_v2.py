"""中文：新版传输的合成宿主集成；English: not native Desktop acceptance."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_routing_v5_context as fixtures
from cp_runtime import budget_v5 as budget, review_v5 as review, routing_hook_v5 as hook
from cp_runtime.routing_context_contract import runtime, MODE_V2
from cp_runtime.routing_contract import ref


class TransportV2Tests(unittest.TestCase):
    def test_copied_header_in_an_alternate_transcript_cannot_attest_final(self):
        self.begin()
        self.read()
        self.final(stop=False)
        alternate = self.f.transcript.with_name("copied-" + self.f.child + ".jsonl")
        alternate.write_bytes(self.f.transcript.read_bytes())
        event = {**self.f.child_data, "hook_event_name": "SubagentStop", "agent_transcript_path": str(alternate)}
        with self.assertRaisesRegex(ValueError, "IDENTITY_LINK_CONFLICT"):
            hook.lifecycle(self.path, event, "SubagentStop")
        self.assertFalse(budget.read_budget(self.path)["context_finals"])
        with self.assertRaisesRegex(ValueError, "NATIVE_FINAL_REQUIRED"):
            review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        review.record_failure_accounting(self.f.review_dir, self.f.pid, evidence_ref=ref("alternate-transcript-denied"))
        with self.assertRaises(ValueError):
            review.close(self.f.review_dir, conclusion="PASS")
        review.close(self.f.review_dir, conclusion="PARTIAL")

    def test_replaced_file_with_identical_header_and_path_is_rejected(self):
        self.begin()
        self.read()
        self.final(stop=False)
        replacement = self.f.transcript.with_name("replacement.jsonl")
        replacement.write_bytes(self.f.transcript.read_bytes())
        replacement.replace(self.f.transcript)
        with self.assertRaisesRegex(ValueError, "IDENTITY_LINK_CONFLICT"):
            self.f.stop()
        self.assertFalse(budget.read_budget(self.path)["context_finals"])

    def test_original_bound_file_can_append_final_normally(self):
        self.f.transcript.write_text(json.dumps(self.f.header) + "\n", encoding="utf-8")
        self.begin()
        self.read()
        payload = {"status": "pass", "findings": [], "checked_scope": ["readme"],
                   "unverified_items": [], "summary": "Native append verified."}
        raw = json.dumps(payload)
        events = [{"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-1"}},
                  {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer",
                    "content": [{"type": "output_text", "text": raw}]}}]
        with self.f.transcript.open("a", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(event) for event in events) + "\n")
        self.response.write_text(raw, encoding="utf-8")
        self.f.stop()
        review.record_semantic(self.f.review_dir, self.f.pid, self.response)

    def test_late_material_is_recorded_but_cannot_be_successful_recovery(self):
        from datetime import datetime, timezone
        self.begin()
        data = self.tool()
        hook.child_tool(self.path, data)
        state = budget.read_budget(self.path)
        first_ms = next(iter(state["context_recovery"].values()))["first_ms"]
        late = datetime.fromtimestamp((first_ms + 5001) / 1000, timezone.utc).isoformat()
        with patch.object(budget, "utc_now", return_value=late):
            with self.assertRaisesRegex(ValueError, "RECOVERY_DEADLINE"):
                self.read(data, pre=False)
            self.final(stop=False)
            original = self.response.read_bytes()
            with self.assertRaisesRegex(ValueError, "FINAL_BINDING"):
                self.f.stop()
            accounted = review.record_failure_accounting(self.f.review_dir, self.f.pid, evidence_ref=ref("late-read-evidence"))
        state = budget.read_budget(self.path)
        self.assertTrue(state["context_deliveries"])
        self.assertEqual("DENIED", next(iter(state["context_recovery"].values()))["status"])
        self.assertFalse(state["context_finals"])
        self.assertEqual(original, self.response.read_bytes())
        stored = json.loads(Path(next(iter(accounted["results"].values()))["result_path"]).read_text())
        self.assertEqual("incomplete", stored["status"])
        self.assertIn("Controller-only failure accounting", stored["summary"])
        with self.assertRaises(ValueError):
            review.close(self.f.review_dir, conclusion="PASS")
        review.close(self.f.review_dir, conclusion="PARTIAL")
        budget.close(self.path, outcome="PARTIAL", evidence_ref=ref("failed-without-refund"))
        state = budget.read_budget(self.path)
        trace = budget.export_trace(self.path, ref(next(iter(state["host_receipts"].values()))))
        self.assertFalse(trace["native_response_verified"])
        self.assertEqual("incomplete", trace["result_status"])
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])

    def test_failure_accounting_cannot_replace_a_verified_success(self):
        self.begin()
        self.read()
        self.final()
        with self.assertRaisesRegex(ValueError, "ACCOUNTING_NO_FAILURE"):
            review.record_failure_accounting(self.f.review_dir, self.f.pid, evidence_ref=ref("invented"))
        review.record_semantic(self.f.review_dir, self.f.pid, self.response)

    def test_cancelled_verified_final_has_separate_accounting_without_rewriting_model_text(self):
        self.begin()
        self.read()
        self.final(outcome="CANCELLED")
        original = self.response.read_bytes()
        result = review.record_failure_accounting(self.f.review_dir, self.f.pid, evidence_ref=ref("native-cancel"))
        stored = json.loads(Path(next(iter(result["results"].values()))["result_path"]).read_text())
        self.assertEqual("incomplete", stored["status"])
        self.assertEqual(original, self.response.read_bytes())
        self.assertTrue(budget.read_budget(self.path)["context_finals"])

    def test_duplicate_concurrent_pretool_preserves_one_grant_and_one_read(self):
        from concurrent.futures import ThreadPoolExecutor
        self.begin()
        data = self.tool()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda _: hook.child_tool(self.path, copy.deepcopy(data)), range(2)))
        self.assertEqual([{}, {}], values)
        self.read(data, pre=False)
        self.final()
        review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        state = budget.read_budget(self.path)
        self.assertEqual(1, len(next(iter(state["context_read_history"].values()))))
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])

    def test_direct_result_cannot_change_native_semantics_with_a_valid_response_hash(self):
        self.begin()
        self.read()
        self.final()
        state = budget.read_budget(self.path)
        rid = next(iter(state["reservations"]))
        response_ref = state["context_finals"][rid]["response_ref"]
        raw_dir = self.f.review_dir / "semantic"
        raw_dir.mkdir()
        (raw_dir / (response_ref[7:] + ".json")).write_bytes(self.response.read_bytes())
        forged = review.result_template(self.f.review_dir, self.f.pid)
        forged.update(status="pass", summary="Changed after the model stopped.", checked_scope=["foreign"])
        target = self.f.f.root / "forged-result.json"
        target.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "RESULT_SEMANTICS_MISMATCH"):
            review.record_result(self.f.review_dir, target, response_ref=response_ref)
        self.assertFalse(budget.read_budget(self.path)["accepted_results"])

    def setUp(self):
        self.f = fixtures.ContextV5Tests(methodName="runTest")
        with patch.object(fixtures, "runtime", lambda reader, python: runtime(reader, python, transport_mode=MODE_V2)):
            self.f.setUp()
        self.path = self.f.path
        self.response = self.f.f.root / "native-final.json"

    def tearDown(self):
        self.f.tearDown()

    def begin(self, receipt=True):
        self.f.reserve()
        self.f.start()
        if receipt:
            self.f.receipt()

    def tool(self, suffix=""):
        value = self.f.tool()
        value["tool_use_id"] += suffix
        return value

    def read(self, data=None, truncate=False, pre=True):
        data = data or self.tool()
        if pre:
            hook.child_tool(self.path, data)
        grant = hook._grant_path(self.path, "desktop-session", self.f.child)
        result = subprocess.run([sys.executable, "-I", "-B", str(fixtures.ROOT / "hooks/review_context_reader.py"), str(grant)],
                                capture_output=True, check=True, timeout=10)
        text = result.stdout.decode("utf-8")
        post = {**data, "hook_event_name": "PostToolUse", "tool_response": text[:-20] if truncate else text}
        hook.child_tool(self.path, post)
        return text, post

    def final(self, payload=None, outcome="UNKNOWN", stop=True):
        payload = payload or {"status": "pass", "findings": [], "checked_scope": ["readme"],
                              "unverified_items": [], "summary": "Bounded material reviewed."}
        raw = json.dumps(payload, ensure_ascii=False)
        events = [self.f.header, {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-1"}},
                  {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer",
                                                       "content": [{"type": "output_text", "text": raw}]}}]
        self.f.transcript.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        self.response.write_text(raw, encoding="utf-8")
        if stop:
            self.f.stop(outcome)
        return self.response

    def test_opt_in_full_flow_uses_native_final_without_copying_nonce(self):
        self.begin()
        self.read()
        self.final()
        result = review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        self.assertEqual(1, len(result["results"]))
        state = budget.read_budget(self.path)
        self.assertEqual(1, len(state["context_finals"]))
        self.assertEqual(1, len(state["reservations"]))
        stored = json.loads(Path(next(iter(result["results"].values()))["result_path"]).read_text())
        self.assertEqual(MODE_V2, stored["transport_mode"])
        self.assertNotIn("context_receipt", stored)
        review.close(self.f.review_dir, conclusion="PASS")

    def test_creation_receipt_pending_is_recoverable_without_extra_dispatch_charge(self):
        self.begin(receipt=False)
        with self.assertRaisesRegex(ValueError, "RETRY_RECEIPT"):
            hook.child_tool(self.path, self.tool())
        self.assertFalse(budget.read_budget(self.path)["context_reads"])
        self.f.receipt()
        self.read(self.tool("-retry"))
        self.final()
        review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        state = budget.read_budget(self.path)
        recovery = next(iter(state["context_recovery"].values()))
        self.assertEqual(2, len(recovery["calls"]))
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])

    def test_truncation_retries_exact_command_and_preserves_both_read_records(self):
        self.begin()
        _, failed_post = self.read(truncate=True)
        self.assertFalse(budget.read_budget(self.path)["context_deliveries"])
        self.read(self.tool("-retry"))
        before = budget.read_budget(self.path)["sequence"]
        hook.child_tool(self.path, failed_post)  # 中文：第一次失败的迟到重复事件。 / English: delayed duplicate of the first failure
        self.assertEqual(before, budget.read_budget(self.path)["sequence"])
        self.final()
        review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        state = budget.read_budget(self.path)
        history = next(iter(state["context_read_history"].values()))
        self.assertEqual(2, len(history))
        self.assertEqual(history[0]["output_ref"], history[1]["output_ref"])
        self.assertNotEqual(history[0]["call_ref"], history[1]["call_ref"])
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])

    def test_duplicate_success_and_stop_are_idempotent(self):
        self.begin()
        _, post = self.read()
        before = budget.read_budget(self.path)["sequence"]
        hook.child_tool(self.path, post)
        self.assertEqual(before, budget.read_budget(self.path)["sequence"])
        self.final()
        before = budget.read_budget(self.path)["sequence"]
        self.f.stop()
        hook.child_tool(self.path, post)
        self.assertEqual(before, budget.read_budget(self.path)["sequence"])

    def test_wrong_command_denies_future_reads_even_if_model_corrects_it(self):
        self.begin()
        data = self.tool()
        data["tool_input"]["command"] += "; Get-Content secret"
        with self.assertRaisesRegex(ValueError, "ONLY_FIXED_READER"):
            hook.child_tool(self.path, data)
        with self.assertRaisesRegex(ValueError, "TERMINAL"):
            hook.child_tool(self.path, self.tool("-corrected"))
        self.assertFalse(budget.read_budget(self.path)["context_reads"])

    def test_wrong_output_or_nonzero_exit_does_not_allow_recovery(self):
        self.begin()
        data = self.tool()
        hook.child_tool(self.path, data)
        with self.assertRaisesRegex(ValueError, "OUTPUT_INTEGRITY"):
            hook.child_tool(self.path, {**data, "hook_event_name": "PostToolUse", "tool_response": {"exit_code": 1, "output": ""}})
        with self.assertRaisesRegex(ValueError, "TERMINAL"):
            hook.child_tool(self.path, self.tool("-retry"))

    def test_missing_or_modified_final_proof_never_accepts_pass(self):
        self.begin()
        self.read()
        self.final(stop=False)
        budget.record_observation(self.path, agent_id=self.f.child, phase="stop")
        with self.assertRaisesRegex(ValueError, "NATIVE_FINAL_REQUIRED"):
            review.record_semantic(self.f.review_dir, self.f.pid, self.response)
        self.f.stop()  # 中文：原生证据无需再次派发即可恢复。 / English: Native evidence can be recovered without another dispatch.
        self.response.write_text(self.response.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "NATIVE_FINAL_REQUIRED"):
            review.record_semantic(self.f.review_dir, self.f.pid, self.response)

    def test_cancelled_child_cannot_turn_bound_final_into_pass(self):
        self.begin()
        self.read()
        self.final(outcome="CANCELLED")
        with self.assertRaisesRegex(ValueError, "CONFLICTS_WITH_HOST_OUTCOME"):
            review.record_semantic(self.f.review_dir, self.f.pid, self.response)

    def test_foreign_final_header_is_rejected_but_attempt_still_stops(self):
        self.begin()
        self.read()
        self.final(stop=False)
        events = [json.loads(line) for line in self.f.transcript.read_text().splitlines()]
        events[0]["payload"]["source"]["subagent"]["thread_spawn"]["parent_thread_id"] = "foreign"
        self.f.transcript.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.f.stop()
        state = budget.read_budget(self.path)
        self.assertFalse(state["context_finals"])
        self.assertEqual("COMPLETED", next(iter(state["reservations"].values()))["state"])

    def test_v1_cannot_consume_v2_recovery_event(self):
        from cp_runtime import context_recovery_v2
        self.begin()
        state = budget.read_budget(self.path)
        self.assertEqual(context_recovery_v2.MODE, state["root_binding"]["context_runtime"]["transport_mode"])
        old = copy.deepcopy(state["root_binding"])
        old["context_runtime"]["transport_mode"] = "desktop-authoritative-context/1"
        other = self.f.f.root / "old-ledger.jsonl"
        budget.initialize(other, declared_identity={**state["identity"], "budget_id": "old"}, root_binding=old,
                          **{key: state[key] for key in ("sources", "execution_mode", "capacity", "role_capacity",
                            "phase_capacity", "phase_plan", "max_parallel", "max_depth")})
        with self.assertRaisesRegex(ValueError, "MODE_REQUIRED"):
            budget.context_recovery(other, {"reservation_id": "x", "agent_ref": ref("x"), "call_ref": ref("x"),
                                           "command_ref": ref("x"), "action": "ATTEMPT", "reason": ""})


if __name__ == "__main__":
    unittest.main()
