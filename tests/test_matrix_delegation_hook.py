"""中文：模拟 Hook 协议集成；所有 session/tool 标识均为测试夹具。

English: Synthetic Hook protocol integration, never evidence of native host dispatch.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import test_dispatch_context as fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import (bind_review_attempt, native_review_message_prefix,
                                         read_budget, record_decision, sha256_ref)  # noqa: E402
from cp_runtime.dispatch_policy import profile_spec  # noqa: E402


class MatrixDelegationHookTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DispatchContextTests(methodName="runTest")
        self.fixture.setUp()
        self.fixture.init()
        self.selection, self.assignment = self.fixture.issue(self.fixture.evidence_request())
        self.native_nonce = "0123456789abcdef" * 4
        record_decision(self.fixture.ledger, dispatch_key="synthetic-attempt", decision="DELEGATE", role="reviewer",
                        approved_profile=self.selection["approved_profile"], reason_code="INDEPENDENT_EVIDENCE_GAIN",
                        selection_scorecard=self.selection, review_assignment=self.assignment)
        bind_review_attempt(self.fixture.ledger, dispatch_key="synthetic-attempt",
                            review_state_ref=sha256_ref("synthetic-review-state"), assignment=self.assignment,
                            native_dispatch_nonce=self.native_nonce)
        self.env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                    "CP_DELEGATION_BUDGET_PATH": str(self.fixture.ledger),
                    "CP_DELEGATION_ENVELOPE_PATH": str(self.fixture.envelope),
                    "CP_DELEGATION_BUDGET_REQUIRED": "1",
                    "CP_ASSISTANT_DATA": str(self.fixture.root / "events"),
                    "CP_CAPABILITY_GATE_ROOT": str(self.fixture.root / "isolated-gates")}
        self.payload = {
            "hook_event_name": "PreToolUse", "tool_name": "spawn_agent", "tool_use_id": "synthetic-tool-call",
            "session_id": "synthetic-session", "turn_id": "synthetic-turn", "cwd": str(self.fixture.repo),
            "tool_input": {"task_name": "synthetic-attempt", "agent_type": "cp_review_data_contract",
                           "model": "gpt-5.6-sol", "reasoning_effort": "low"},
        }

    def tearDown(self):
        self.fixture.tearDown()

    def invoke(self, payload=None, env=None):
        value = payload if payload is not None else self.payload
        result = subprocess.run([sys.executable, "-B", str(ROOT / "hooks" / "cp_hook.py"), value["hook_event_name"]],
                                input=json.dumps(value), cwd=self.fixture.repo, env=env or self.env, text=True,
                                encoding="utf-8", errors="replace", capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def denied(self, payload, env=None):
        output = self.invoke(payload, env).stdout
        self.assertEqual("deny", json.loads(output)["hookSpecificOutput"]["permissionDecision"], output)

    def native_payload(self):
        native = copy.deepcopy(self.payload)
        native["tool_input"].pop("task_name")
        native["tool_input"].update(fork_context=False, message=native_review_message_prefix(self.native_nonce) + "Synthetic review")
        return native

    def test_v3_hook_consumes_scored_permit_once_and_projects_bound_identity(self):
        self.assertEqual("", self.invoke().stdout.strip())
        self.assertEqual("", self.invoke().stdout.strip())
        state = read_budget(self.fixture.ledger)
        self.assertEqual(1, state["usage"]["dispatches"])
        self.assertEqual(10, state["usage"]["units"])
        rows = []
        for path in (self.fixture.root / "events" / "synthetic-project").rglob("*.jsonl"):
            rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        events = [item for item in rows if item.get("event_type") == "PRE_TOOL_GUARD"]
        self.assertTrue(events)
        self.assertEqual("synthetic-task", events[-1]["task_id"])
        self.assertEqual("sol-low", events[-1]["approved_dispatch_profile"])

    def test_desktop_concatenated_name_preserves_v3_units_and_receipt(self):
        payload = {**self.payload, "tool_name": "collaborationspawn_agent"}
        self.invoke(payload)
        self.invoke(payload)
        state = read_budget(self.fixture.ledger)
        self.assertEqual(1, state["usage"]["dispatches"])
        self.assertEqual(10, state["usage"]["units"])
        self.invoke({**payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"agent_id": "synthetic-child"}})
        self.assertEqual(1, len(read_budget(self.fixture.ledger)["host_receipts"]))

    def test_changed_role_tuple_or_host_call_cannot_reuse_permit(self):
        self.invoke()
        before = self.fixture.ledger.read_bytes()
        for key, value in (("agent_type", "cp_review_security_access"), ("reasoning_effort", "medium"),
                           ("agent_type", "worker"), ("agent_type", "cp_review_spoof")):
            payload = copy.deepcopy(self.payload)
            payload["tool_input"][key] = value
            self.denied(payload)
        self.denied({**self.payload, "tool_use_id": "another-host-call"})
        self.assertEqual(before, self.fixture.ledger.read_bytes())

    def test_wrong_session_cwd_or_missing_envelope_fail_closed_before_reservation(self):
        before = self.fixture.ledger.read_bytes()
        self.denied({**self.payload, "session_id": "other-session"})
        self.denied({**self.payload, "cwd": str(self.fixture.root)})
        self.denied(self.payload, {**self.env, "CP_DELEGATION_ENVELOPE_PATH": ""})
        self.assertEqual(before, self.fixture.ledger.read_bytes())

    def test_stale_baseline_and_implicit_model_are_rejected(self):
        before = self.fixture.ledger.read_bytes()
        payload = copy.deepcopy(self.payload)
        payload["tool_input"].pop("model")
        self.denied(payload)
        (self.fixture.repo / "README.md").write_text("Changed after selection\n", encoding="utf-8")
        self.denied(self.payload)
        self.assertEqual(before, self.fixture.ledger.read_bytes())

    def test_started_attempt_cannot_be_dispatched_again_and_foreign_stop_cannot_complete(self):
        self.invoke()
        self.invoke({**self.payload, "hook_event_name": "PostToolUse", "tool_response": {"agent_id": "synthetic-child"}})
        reservation = next(iter(read_budget(self.fixture.ledger)["reservations"]))
        start = {"hook_event_name": "SubagentStart", "reservation_id": reservation,
                 "agent_id": "synthetic-child", "session_id": "synthetic-session", "cwd": str(self.fixture.repo)}
        self.invoke(start)
        self.assertEqual("STARTED", read_budget(self.fixture.ledger)["reservations"][reservation]["state"])
        self.denied(self.payload)
        stop = {**start, "hook_event_name": "SubagentStop", "terminal_outcome": "PASS", "session_id": "foreign-session"}
        result = self.invoke(stop)
        self.assertIn("RECONCILIATION_FAILED", result.stderr)
        self.assertEqual("STARTED", read_budget(self.fixture.ledger)["reservations"][reservation]["state"])

    def test_supplied_reservation_id_cannot_bypass_native_receipt_association(self):
        self.invoke()
        rid = next(iter(read_budget(self.fixture.ledger)["reservations"]))
        value = {"reservation_id":rid, "agent_id":"foreign-child", "session_id":"synthetic-session", "cwd":str(self.fixture.repo)}
        self.invoke({**value, "hook_event_name":"SubagentStart"})
        self.invoke({**value, "hook_event_name":"SubagentStop", "terminal_outcome":"PASS"})
        state = read_budget(self.fixture.ledger)
        self.assertEqual("RESERVED", state["reservations"][rid]["state"])
        self.assertFalse(state["association_complete"])

    def test_policy_only_six_new_tuples_work_only_for_registered_reviewers(self):
        env = {**self.env, "CP_DELEGATION_BUDGET_PATH": "", "CP_DELEGATION_BUDGET_REQUIRED": "0"}
        for profile in ("sol-low", "sol-medium", "sol-high", "astra-low", "astra-medium", "astra-high"):
            spec = profile_spec(profile)
            payload = copy.deepcopy(self.payload)
            payload["tool_input"].update(model=spec["model"], reasoning_effort=spec["effort"])
            self.assertEqual("", self.invoke(payload, env).stdout.strip())
            payload["tool_input"]["agent_type"] = "explorer"
            self.denied(payload, env)
        self.assertEqual(0, read_budget(self.fixture.ledger)["usage"]["dispatches"])

    def test_native_callbacks_without_reservation_join_after_late_receipt(self):
        self.invoke()
        rid = next(iter(read_budget(self.fixture.ledger)["reservations"]))
        lifecycle = {"session_id": "synthetic-session", "cwd": str(self.fixture.repo), "agent_id": "synthetic-child"}
        self.invoke({**lifecycle, "hook_event_name": "SubagentStop", "terminal_outcome": "PASS"})
        self.invoke({**lifecycle, "hook_event_name": "SubagentStart"})
        self.assertEqual("RESERVED", read_budget(self.fixture.ledger)["reservations"][rid]["state"])
        post = {**self.payload, "hook_event_name": "PostToolUse", "tool_response": {"agent_id": "synthetic-child"}}
        self.invoke(post)
        before = self.fixture.ledger.read_bytes()
        self.invoke(post)
        self.assertEqual(before, self.fixture.ledger.read_bytes())
        state = read_budget(self.fixture.ledger)
        self.assertEqual("COMPLETED", state["reservations"][rid]["state"])
        self.assertEqual(1, state["usage"]["dispatches"])

    def test_unknown_tool_reply_and_generic_status_cannot_complete_or_refund(self):
        self.invoke()
        for response in ({}, {"status": "failed"}, "timeout", {"status": "success"}):
            self.invoke({**self.payload, "hook_event_name": "PostToolUse", "tool_response": response})
        state = read_budget(self.fixture.ledger)
        self.assertEqual({}, state["host_receipts"])
        self.assertEqual("RESERVED", next(iter(state["reservations"].values()))["state"])

    def test_native_request_without_task_name_uses_one_bound_permit_and_receipt(self):
        native = self.native_payload()
        self.assertEqual("", self.invoke(native).stdout.strip())
        self.assertEqual("", self.invoke(native).stdout.strip())
        state = read_budget(self.fixture.ledger)
        self.assertEqual(1, state["usage"]["dispatches"])
        self.invoke({**native, "hook_event_name":"PostToolUse", "tool_response":json.dumps({"agent_id":"native-child"})})
        before = self.fixture.ledger.read_bytes()
        self.denied(native)
        self.assertEqual(before, self.fixture.ledger.read_bytes())
        for phase in ("SubagentStop", "SubagentStart"):
            self.invoke({"hook_event_name":phase,"agent_id":"native-child","session_id":"synthetic-session",
                         "cwd":str(self.fixture.repo),"terminal_outcome":"PASS"})
        self.assertTrue(read_budget(self.fixture.ledger)["association_complete"])

    def test_native_request_cannot_guess_between_two_matching_permits(self):
        assignment = {**self.assignment, "reviewer":"second-reviewer"}
        record_decision(self.fixture.ledger, dispatch_key="second-attempt", decision="DELEGATE", role="reviewer",
                        approved_profile=self.selection["approved_profile"], reason_code="INDEPENDENT_EVIDENCE_GAIN",
                        selection_scorecard=self.selection, review_assignment=assignment)
        bind_review_attempt(self.fixture.ledger, dispatch_key="second-attempt",
                            review_state_ref=sha256_ref("synthetic-review-state"), assignment=assignment)
        native = self.native_payload()
        native["tool_input"].pop("message")
        before = self.fixture.ledger.read_bytes()
        self.denied(native)
        self.assertEqual(before, self.fixture.ledger.read_bytes())
        self.assertEqual("", self.invoke(self.native_payload()).stdout.strip())
        self.assertEqual(sha256_ref("synthetic-attempt"), next(iter(read_budget(self.fixture.ledger)["reservations"].values()))["dispatch_ref"])

    def test_native_reference_header_is_explicit_and_never_scans_the_body(self):
        native = self.native_payload()
        prefix = native_review_message_prefix(self.native_nonce)
        before = self.fixture.ledger.read_bytes()
        for message in (None, "", "\n" + prefix, prefix[:-2], prefix.replace("\n\n", "\n" + prefix),
                        prefix.replace(self.native_nonce, "b" * 64), prefix.replace("\n", "\r\n"),
                        "Ordinary text\n" + prefix, prefix.replace(self.native_nonce, self.native_nonce[:-1])):
            changed = copy.deepcopy(native)
            changed["tool_input"]["message"] = message
            self.denied(changed)
        conflict = copy.deepcopy(self.payload)
        conflict["tool_input"]["message"] = prefix
        self.denied(conflict)
        self.assertEqual(before, self.fixture.ledger.read_bytes())
        self.assertNotIn(self.native_nonce.encode(), before)

    def test_child_missing_agent_id_cannot_claim_without_reference_or_reuse_consumed_reference(self):
        native = self.native_payload()
        missing = copy.deepcopy(native)
        missing["tool_input"].pop("message")
        before = self.fixture.ledger.read_bytes()
        self.denied(missing)
        self.assertEqual(before, self.fixture.ledger.read_bytes())
        self.invoke(native)
        before = self.fixture.ledger.read_bytes()
        self.denied({**native, "tool_use_id": "nested-other-call"})
        self.assertEqual(before, self.fixture.ledger.read_bytes())

    def test_native_request_requires_exact_role_profile_and_fresh_baseline(self):
        native = self.native_payload()
        before = self.fixture.ledger.read_bytes()
        self.denied({**native,"agent_id":"nested-caller"})
        for key, value in (("reasoning_effort","medium"),("agent_type","cp_review_security_access"), ("agent_type","worker")):
            changed = copy.deepcopy(native)
            changed["tool_input"][key] = value
            self.denied(changed)
        (self.fixture.repo / "README.md").write_text("New baseline",encoding="utf-8")
        self.denied(native)
        self.assertEqual(before, self.fixture.ledger.read_bytes())


if __name__ == "__main__":
    unittest.main()
