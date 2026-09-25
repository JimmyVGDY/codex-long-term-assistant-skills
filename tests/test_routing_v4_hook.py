"""中文：V4 Hook 管线回归；所有宿主输入均为合成协议夹具。

English: V4 hook pipeline regression with synthetic host inputs.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4
from cp_runtime import routing_registry_v4 as registry
from cp_runtime.delegation_budget import read_budget
import test_routing_v4_context as context_fixtures


class V4HookTests(unittest.TestCase):
    def setUp(self):
        self.fixture = context_fixtures.ContextTests(methodName="runTest")
        self.fixture.setUp()
        self.prepared = budget_v4.prepare(
            self.fixture.path, self.fixture.request, dispatch_key="eval_one", depth=1,
            snapshot_loader=self.fixture.loader)
        self.payload = {
            "hook_event_name": "PreToolUse", "tool_name": "spawn_agent", "tool_use_id": "host-one",
            "session_id": "desktop-session", "turn_id": "synthetic-turn", "cwd": str(self.fixture.repo),
            "tool_input": {**self.prepared["request_parameters"], "task_name": "eval_one",
                           "fork_turns": "none", "message": json.dumps("synthetic-prompt-0")},
        }
        self.env = {
            **os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "CP_DELEGATION_BUDGET_PATH": str(self.fixture.path),
            "CP_DELEGATION_ENVELOPE_PATH": str(self.fixture.envelope),
            "CP_DELEGATION_BUDGET_REQUIRED": "1",
            "CP_ASSISTANT_DATA": str(self.fixture.root / "events"),
            "CP_CAPABILITY_GATE_ROOT": str(self.fixture.root / "isolated-gates"),
            "CP_ROUTING_BINDINGS_ROOT": str(self.fixture.root / "bindings"),
        }

    def tearDown(self):
        self.fixture.tearDown()

    def invoke(self, payload=None):
        payload = payload or self.payload
        outcome = subprocess.run(
            [sys.executable, "-B", str(ROOT / "hooks" / "cp_hook.py"), payload["hook_event_name"]],
            input=json.dumps(payload), cwd=self.fixture.repo, env=self.env, text=True,
            encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(0, outcome.returncode, outcome.stderr)
        return json.loads(outcome.stdout) if outcome.stdout.strip() else {}

    def denied(self, payload):
        value = self.invoke(payload)
        self.assertEqual("deny", value["hookSpecificOutput"]["permissionDecision"])

    def test_new_tuple_reserves_through_existing_hook_and_legacy_reader_dispatch(self):
        self.assertEqual({}, self.invoke())
        state = read_budget(self.fixture.path)
        self.assertEqual("4.0", state["schema_version"])
        self.assertEqual(1, len(state["reservations"]))

    def test_message_or_context_inheritance_cannot_change_approved_experiment(self):
        for key, value in (("message", "different prompt"), ("fork_turns", "all"),
                           ("model", "gpt-6-astra"), ("agent_type", "worker")):
            changed = copy.deepcopy(self.payload)
            changed["tool_input"][key] = value
            self.denied(changed)
        self.assertFalse(read_budget(self.fixture.path)["reservations"])

    def test_named_and_nonce_routes_cannot_be_combined(self):
        changed = copy.deepcopy(self.payload)
        changed["tool_input"]["message"] = self.prepared["native_message_prefix"] + changed["tool_input"]["message"]
        self.denied(changed)
        changed["tool_input"].pop("task_name")
        self.assertEqual({}, self.invoke(changed))

    def test_foreign_root_or_nested_caller_is_rejected_before_charge(self):
        self.denied({**self.payload, "session_id": "foreign-session"})
        self.denied({**self.payload, "agent_id": "nested-agent"})
        self.assertFalse(read_budget(self.fixture.path)["reservations"])

    def test_out_of_order_lifecycle_keeps_awaiting_result_and_never_guesses_pass(self):
        self.invoke()
        self.invoke({"hook_event_name": "SubagentStop", "session_id": "desktop-session",
                     "cwd": str(self.fixture.repo), "agent_id": "synthetic-agent"})
        self.invoke({**self.payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"agent_id": "synthetic-agent"}})
        state = read_budget(self.fixture.path)
        attempt = next(iter(state["reservations"].values()))
        self.assertEqual("COMPLETED", attempt["state"])
        self.assertEqual("UNKNOWN", attempt["outcome"])
        self.assertEqual("AWAITING_RESULT", state["phase_plan"]["slots"][0]["status"])
        self.assertFalse(state["accepted_results"])

    def test_desktop_task_tree_receipt_uses_exact_requested_leaf(self):
        payload = {**self.payload, "tool_name": "collaboration.spawn_agent"}
        self.invoke(payload)
        self.invoke({**payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/wrong_task"}})
        self.assertFalse(read_budget(self.fixture.path)["host_receipts"])
        self.invoke({**payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/eval_one"}})
        self.assertEqual(1, len(read_budget(self.fixture.path)["host_receipts"]))

    def test_concatenated_desktop_name_reserves_and_reconciles_once(self):
        payload = {**self.payload, "tool_name": "collaborationspawn_agent"}
        self.bind_registry()
        self.assertEqual({}, self.invoke(payload))
        self.assertEqual(1, len(read_budget(self.fixture.path)["reservations"]))
        receipt = {**payload, "hook_event_name": "PostToolUse",
                   "tool_response": {"task_name": "/root/eval_one"}}
        self.invoke({**receipt, "tool_response": {"task_name": "/root/wrong_task"}})
        self.assertFalse(read_budget(self.fixture.path)["host_receipts"])
        self.invoke(receipt)
        before = self.fixture.path.read_bytes()
        self.invoke(receipt)
        self.assertEqual(before, self.fixture.path.read_bytes())
        self.assertEqual(1, len(read_budget(self.fixture.path)["host_receipts"]))

    def test_concatenated_name_cannot_bypass_the_approved_message(self):
        payload = copy.deepcopy(self.payload)
        payload["tool_name"] = "collaborationspawn_agent"
        payload["tool_input"]["message"] = "unapproved message"
        self.denied(payload)
        self.assertFalse(read_budget(self.fixture.path)["reservations"])

    def test_other_tool_names_are_not_matched_by_delegation_suffix(self):
        for name in ("mcp__foreign__collaborationspawn_agent", "collaborationspawn_agent_extra"):
            self.assertEqual({}, self.invoke({**self.payload, "tool_name": name}))
        self.assertFalse(read_budget(self.fixture.path)["reservations"])

    def test_cancelled_subagent_stop_cannot_be_recorded_as_a_pass(self):
        from cp_runtime.routing_contract import RoutingError, ref
        self.invoke()
        self.invoke({**self.payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"agent_id": "cancelled-agent"}})
        self.invoke({"hook_event_name": "SubagentStop", "session_id": "desktop-session",
                     "cwd": str(self.fixture.repo), "agent_id": "cancelled-agent",
                     "terminal_outcome": "CANCELLED"})
        state = read_budget(self.fixture.path)
        attempt = next(iter(state["reservations"].values()))
        with self.assertRaisesRegex(RoutingError, "CONFLICTS_WITH_HOST_OUTCOME"):
            budget_v4.accept_result(
                self.fixture.path, reservation_id=attempt["reservation_id"],
                result_ref=ref("invalid-pass"), status="pass", response_ref=ref("response"),
                baseline_sha256=self.fixture.request["baseline_sha256"])
        self.assertFalse(read_budget(self.fixture.path)["accepted_results"])

    def desktop_identity(self):
        desktop = self.fixture.root / "desktop-home"
        sessions = desktop / "sessions"
        sessions.mkdir(parents=True)
        self.env["CODEX_HOME"] = str(desktop)
        agent_id = "12345678-1234-1234-1234-123456789012"
        path = sessions / f"rollout-{agent_id}.jsonl"
        header = {"type": "session_meta", "payload": {"id": agent_id, "cwd": str(self.fixture.repo),
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": "desktop-session", "depth": 1,
                "agent_path": "/root/eval_one", "agent_role": self.prepared["request_parameters"]["agent_type"]}}}}}
        return agent_id, path, header

    def assert_task_tree_identity(self, stop_first):
        from cp_runtime.routing_contract import ref
        agent_id, path, header = self.desktop_identity()
        path.write_text(json.dumps(header) + "\nPRIVATE_BODY_MUST_NOT_BE_READ\n", encoding="utf-8")
        self.invoke()
        start = {"hook_event_name": "SubagentStart", "session_id": "desktop-session", "agent_id": agent_id,
                 "cwd": str(self.fixture.repo), "agent_type": self.prepared["request_parameters"]["agent_type"]}
        stop = {**start, "hook_event_name": "SubagentStop", "agent_transcript_path": str(path)}
        receipt = {**self.payload, "hook_event_name": "PostToolUse", "tool_response": {"task_name": "/root/eval_one"}}
        self.invoke(start)
        for event in ((stop, receipt) if stop_first else (receipt, stop)):
            self.invoke(event)
        self.invoke(stop)
        self.invoke(receipt)
        state = read_budget(self.fixture.path)
        attempt = next(iter(state["reservations"].values()))
        self.assertEqual("COMPLETED", attempt["state"])
        self.assertEqual("UNKNOWN", attempt["outcome"])
        self.assertEqual(0, state["_usage_cache"]["active"])
        self.assertEqual(1, state["_usage_cache"]["resources"]["attempts"])
        self.assertEqual(ref(agent_id), budget_v4.effective_agent_ref(state, attempt["reservation_id"]))
        self.assertEqual("AWAITING_RESULT", state["phase_plan"]["slots"][0]["status"])
        raw = self.fixture.path.read_text(encoding="utf-8")
        self.assertNotIn(agent_id, raw)
        self.assertNotIn("PRIVATE_BODY_MUST_NOT_BE_READ", raw)
        self.assertNotIn(str(path), raw)

    def test_desktop_task_tree_receipt_links_to_uuid_stop(self):
        self.assert_task_tree_identity(False)

    def test_desktop_uuid_stop_before_task_tree_receipt_links_once(self):
        self.assert_task_tree_identity(True)

    def test_task_tree_identity_rejects_foreign_metadata_and_paths(self):
        agent_id, path, header = self.desktop_identity()
        self.invoke()
        self.invoke({**self.payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/eval_one"}})
        stop = {"hook_event_name": "SubagentStop", "session_id": "desktop-session", "agent_id": agent_id,
                "cwd": str(self.fixture.repo), "agent_type": self.prepared["request_parameters"]["agent_type"],
                "agent_transcript_path": str(path)}
        for key, value in (("parent_thread_id", "foreign-session"), ("agent_role", "worker"),
                           ("agent_path", "/root/foreign"), ("depth", 2)):
            changed = copy.deepcopy(header)
            changed["payload"]["source"]["subagent"]["thread_spawn"][key] = value
            path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
            self.invoke(stop)
        outside = self.fixture.repo / path.name
        outside.write_text(json.dumps(header) + "\n", encoding="utf-8")
        self.invoke({**stop, "agent_transcript_path": str(outside)})
        path.write_text(" " * 131073 + "\n", encoding="utf-8")
        self.invoke(stop)
        state = read_budget(self.fixture.path)
        self.assertFalse(state["host_identity_links"])
        self.assertEqual(1, state["_usage_cache"]["active"])
        self.assertFalse(state["accepted_results"])

    def test_generic_status_does_not_create_receipt_or_refund(self):
        self.invoke()
        self.invoke({**self.payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"status": "failed"}})
        state = read_budget(self.fixture.path)
        self.assertFalse(state["host_receipts"])
        self.assertGreater(state["_usage_cache"]["resources"]["units"], 0)

    def bind_registry(self):
        directory = Path(self.env["CP_ROUTING_BINDINGS_ROOT"])
        registry.bind(self.fixture.path, cwd=str(self.fixture.repo), host_session_id="desktop-session",
                      directory=directory)
        self.env.pop("CP_DELEGATION_BUDGET_PATH")
        self.env.pop("CP_DELEGATION_ENVELOPE_PATH")
        return directory

    def test_registered_task_reserves_without_parent_environment_mutation(self):
        self.bind_registry()
        self.assertEqual({}, self.invoke())
        self.assertEqual(1, len(read_budget(self.fixture.path)["reservations"]))

    def test_corrupt_entry_fails_closed_and_other_sessions_remain_unbound(self):
        directory = self.bind_registry()
        self.assertIsNone(registry.lookup(cwd=str(self.fixture.repo), host_session_id="other-session",
                                          directory=directory))
        entry = next(directory.glob("*.json"))
        entry.write_text("broken", encoding="utf-8")
        self.denied(self.payload)
        self.assertFalse(read_budget(self.fixture.path)["reservations"])

    def test_absent_registry_under_cwd_does_not_disable_unbound_lifecycle(self):
        from cp_runtime.common import RuntimeContractError
        inside = self.fixture.repo / "not-configured"
        self.assertIsNone(registry.lookup(cwd=str(self.fixture.repo), host_session_id="desktop-session",
                                          directory=inside))
        self.assertFalse(inside.exists())
        with self.assertRaises(RuntimeContractError):
            registry.bind(self.fixture.path, cwd=str(self.fixture.repo), host_session_id="desktop-session",
                          directory=inside)

    def test_bound_v4_reentry_cannot_bypass_a_new_permit_or_mutate_the_trial_prompt(self):
        for name in ("collaboration.followup_task", "collaboration.send_message",
                     "collaborationfollowup_task", "collaborationsend_message", "send_input", "resume_agent"):
            payload = {**self.payload, "tool_name": name,
                       "tool_input": {"target": "/root/prior_agent", "message": "new work"}}
            self.denied(payload)
        self.assertFalse(read_budget(self.fixture.path)["reservations"])
        self.env.pop("CP_DELEGATION_BUDGET_PATH")
        self.env.pop("CP_DELEGATION_BUDGET_REQUIRED")
        self.assertEqual({}, self.invoke(payload))

    def test_ordinary_roles_cannot_inherit_an_unknown_parent_tuple(self):
        self.env.pop("CP_DELEGATION_BUDGET_PATH")
        self.env.pop("CP_DELEGATION_BUDGET_REQUIRED")
        for role in ("worker", "explorer"):
            for omitted in ("model", "reasoning_effort"):
                params = {"agent_type": role, "model": "gpt-5.6-luna", "reasoning_effort": "low"}
                params.pop(omitted)
                self.denied({**self.payload, "tool_input": params})

    def test_registry_cannot_replace_or_retire_an_active_budget(self):
        directory = self.bind_registry()
        from cp_runtime.routing_contract import RoutingError, ref
        with self.assertRaisesRegex(RoutingError, "ACTIVE_LEDGER"):
            registry.retire(cwd=str(self.fixture.repo), host_session_id="desktop-session", directory=directory)
        self.env["CP_DELEGATION_BUDGET_PATH"] = str(self.fixture.root / "another.jsonl")
        self.denied(self.payload)
        budget_v4.close(self.fixture.path, outcome="CANCELLED", evidence_ref=ref("synthetic-cancellation"))
        registry.retire(cwd=str(self.fixture.repo), host_session_id="desktop-session", directory=directory)
        self.env.pop("CP_DELEGATION_BUDGET_PATH")
        self.denied(self.payload)
        self.assertEqual(self.fixture.path.resolve(), registry.lookup(cwd=str(self.fixture.repo),
                         host_session_id="desktop-session", directory=directory))


if __name__ == "__main__":
    unittest.main()
