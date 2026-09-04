from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import (  # noqa: E402
    initialize_budget, mark_started, read_budget, record_decision, reserve_budget,
)

FINGERPRINT = "sha256:" + "a" * 64


class DelegationHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temp.name) / "delegation-budget-v1.jsonl"
        initialize_budget(self.ledger, budget_id="BUDGET-HOOK", task_id="TASK-HOOK",
                          project_id="project-hook", repo_fingerprint=FINGERPRINT,
                          budget_class="STANDARD", default_model_profile="luna-low")
        self.hook = ROOT / "hooks" / "cp_hook.py"
        self.env = os.environ.copy()
        self.env["CP_DELEGATION_BUDGET_PATH"] = str(self.ledger)
        self.env["CP_ASSISTANT_DATA"] = str(Path(self.temp.name) / "events")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, hook: str, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(self.hook), hook], input=json.dumps(payload),
                              text=True, encoding="utf-8", capture_output=True,
                              env=self.env, timeout=10)

    def controller(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        script = ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_controller.py"
        result = subprocess.run([sys.executable, str(script), *args], text=True, encoding="utf-8",
                                errors="replace", capture_output=True, timeout=10)
        if ok and result.returncode:
            self.fail(result.stdout + result.stderr)
        if not ok and result.returncode == 0:
            self.fail("expected reviewer controller failure")
        return result

    def test_pretool_consumes_explicit_permit_and_replay_is_idempotent(self) -> None:
        record_decision(self.ledger, dispatch_key="worker-permit", decision="DELEGATE", role="worker",
                        requested_profile="luna-low", reason_code="SEMANTIC_COMPLEXITY")
        payload = {
            "hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
            "tool_use_id": "host-tool-1", "cwd": str(ROOT),
            "tool_input": {"task_name": "worker-permit", "agent_type": "worker",
                           "model": "gpt-5.6-luna", "reasoning_effort": "low"},
        }
        for _ in range(2):
            result = self.invoke("PreToolUse", payload)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn('"permissionDecision": "deny"', result.stdout)
        self.assertEqual(1, read_budget(self.ledger)["usage"]["dispatches"])

    def test_missing_permit_role_mismatch_and_missing_tool_id_fail_closed(self) -> None:
        record_decision(self.ledger, dispatch_key="review-permit", decision="DELEGATE", role="reviewer",
                        requested_profile="luna-low", reason_code="INDEPENDENT_EVIDENCE_GAIN")
        base = {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent", "tool_use_id": "tool-x",
                "cwd": str(ROOT), "tool_input": {"task_name": "review-permit", "agent_type": "worker",
                                                    "model": "gpt-5.6-luna", "reasoning_effort": "low"}}
        self.assertIn('"permissionDecision": "deny"', self.invoke("PreToolUse", base).stdout)
        base["tool_input"]["task_name"] = "missing-permit"
        self.assertIn('"permissionDecision": "deny"', self.invoke("PreToolUse", base).stdout)
        base.pop("tool_use_id")
        self.assertIn('"permissionDecision": "deny"', self.invoke("PreToolUse", base).stdout)

    def test_required_budget_without_ledger_fails_closed(self) -> None:
        ledger = self.env.pop("CP_DELEGATION_BUDGET_PATH")
        self.env["CP_DELEGATION_BUDGET_REQUIRED"] = "1"
        try:
            payload = {
                "hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
                "tool_use_id": "required-tool", "cwd": str(ROOT),
                "tool_input": {"task_name": "required", "agent_type": "worker",
                               "model": "gpt-5.6-luna", "reasoning_effort": "low"},
            }
            self.assertIn('"permissionDecision": "deny"', self.invoke("PreToolUse", payload).stdout)
        finally:
            self.env["CP_DELEGATION_BUDGET_PATH"] = ledger
            self.env.pop("CP_DELEGATION_BUDGET_REQUIRED", None)

    def test_unified_exec_is_not_a_dispatch_and_cannot_consume_a_permit(self) -> None:
        record_decision(self.ledger, dispatch_key="nested-dispatch", decision="DELEGATE", role="worker",
                        requested_profile="luna-low", reason_code="SEMANTIC_COMPLEXITY")
        payload = {
            "hook_event_name": "PreToolUse", "tool_name": "unified_exec",
            "tool_use_id": "unified-tool", "cwd": str(ROOT),
            "tool_input": {"source": "await tools.spawn_agent({task_name: 'nested-dispatch'})"},
        }
        result = self.invoke("PreToolUse", payload)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        state = read_budget(self.ledger)
        self.assertEqual(0, state["usage"]["dispatches"])
        self.assertEqual(1, len(state["decisions"]))
        self.assertEqual({}, state["reservations"])

    def test_pretool_alias_conflicts_fail_closed_with_registered_envelope(self) -> None:
        top_level = {
            "hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
            "toolName": "shell", "tool_input": {},
        }
        result = self.invoke("PreToolUse", top_level)
        denial = json.loads(result.stdout)
        self.assertEqual("PreToolUse", denial["hookSpecificOutput"]["hookEventName"])
        self.assertEqual("deny", denial["hookSpecificOutput"]["permissionDecision"])

        nested = {
            "hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
            "tool_use_id": "alias-conflict", "tool_input": {
                "task_name": "alias-conflict", "agent_type": "worker",
                "model": "gpt-5.6-luna", "modelName": "gpt-5.6-sol",
                "reasoning_effort": "low",
            },
        }
        result = self.invoke("PreToolUse", nested)
        self.assertEqual("deny", json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"])

    def test_stop_variants_always_emit_neutral_json_on_observation_conflict(self) -> None:
        for hook in ("Stop", "SubagentStop"):
            with self.subTest(hook=hook):
                payload = {
                    "hook_event_name": hook,
                    "session_id": "one", "sessionId": "two",
                    "cwd": str(ROOT),
                }
                result = self.invoke(hook, payload)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual({}, json.loads(result.stdout))

    def test_lifecycle_reconciles_only_explicit_reservation(self) -> None:
        record_decision(self.ledger, dispatch_key="lifecycle", decision="DELEGATE", role="explorer",
                        requested_profile="luna-low", reason_code="SEMANTIC_COMPLEXITY")
        reserved = reserve_budget(self.ledger, dispatch_key="lifecycle", host_dispatch_id="life-tool",
                                  requested_profile="luna-low", request_basis="explicit-request", role="explorer")
        start = {"hook_event_name": "SubagentStart", "reservation_id": reserved["reservation_id"],
                 "agent_id": "child-agent", "agent_type": "explorer", "cwd": str(ROOT)}
        self.assertEqual(0, self.invoke("SubagentStart", start).returncode)
        self.assertEqual("STARTED", read_budget(self.ledger)["reservations"][reserved["reservation_id"]]["state"])
        stop = {"hook_event_name": "SubagentStop", "reservation_id": reserved["reservation_id"],
                "agent_id": "child-agent", "terminal_outcome": "PASS", "cwd": str(ROOT)}
        self.assertEqual(0, self.invoke("SubagentStop", stop).returncode)
        self.assertEqual("COMPLETED", read_budget(self.ledger)["reservations"][reserved["reservation_id"]]["state"])

    def test_unassociated_start_does_not_guess_or_consume_reservation(self) -> None:
        record_decision(self.ledger, dispatch_key="unassociated", decision="DELEGATE", role="worker",
                        requested_profile="luna-low", reason_code="SEMANTIC_COMPLEXITY")
        reserved = reserve_budget(self.ledger, dispatch_key="unassociated", host_dispatch_id="unassociated-tool",
                                  requested_profile="luna-low", request_basis="explicit-request", role="worker")
        payload = {"hook_event_name": "SubagentStart", "agent_id": "unknown-child",
                   "agent_type": "worker", "cwd": str(ROOT)}
        self.assertEqual(0, self.invoke("SubagentStart", payload).returncode)
        state = read_budget(self.ledger)
        self.assertEqual("RESERVED", state["reservations"][reserved["reservation_id"]]["state"])
        self.assertFalse(state["association_complete"])

    def test_reviewer_controller_links_permit_without_double_charging(self) -> None:
        record_decision(self.ledger, dispatch_key="review-budget-key", decision="DELEGATE", role="reviewer",
                        requested_profile="luna-medium", reason_code="INDEPENDENT_EVIDENCE_GAIN")
        review = Path(self.temp.name) / "review"
        common = ("--review-dir", str(review))
        self.controller("init", *common, "--boundary-id", "BOUNDARY-1",
                        "--delegation-ledger", str(self.ledger), "--delegation-budget-id", "BUDGET-HOOK")
        self.controller("route", *common, "--phase", "post", "--decision", "DELEGATE",
                        "--reason-code", "INDEPENDENT_EVIDENCE_GAIN", "--reason", "独立证据")
        self.controller("plan", *common, "--phase", "post", "--depth", "1", "--reviewers", "reviewer-one",
                        "--purpose", "复审", "--effort-tier", "balanced")
        self.controller("dispatch", *common, "--phase", "post", "--round", "1",
                        "--reviewer", "reviewer-one", "--scope", "bounded",
                        "--model-profile", "luna-medium", "--delegation-dispatch-key", "review-budget-key")
        before = read_budget(self.ledger)
        self.assertEqual(0, before["usage"]["dispatches"])
        reserved = reserve_budget(self.ledger, dispatch_key="review-budget-key", host_dispatch_id="review-tool",
                                  requested_profile="luna-medium", request_basis="explicit-request", role="reviewer")
        missing_attribution = self.controller(
            "result", *common, "--phase", "post", "--round", "1",
            "--reviewer", "reviewer-one", "--status", "pass", "--summary", "完成",
            ok=False,
        )
        self.assertIn("--delegation-reservation-id", missing_attribution.stderr)
        reserved_only = self.controller(
            "result", *common, "--phase", "post", "--round", "1",
            "--reviewer", "reviewer-one", "--status", "pass", "--summary", "完成",
            "--delegation-reservation-id", reserved["reservation_id"], ok=False,
        )
        self.assertIn("Reviewer reservation", reserved_only.stderr)
        mark_started(self.ledger, reservation_id=reserved["reservation_id"],
                     agent_id="reviewer-one")
        self.controller("result", *common, "--phase", "post", "--round", "1",
                        "--reviewer", "reviewer-one", "--status", "pass", "--summary", "完成",
                        "--delegation-reservation-id", reserved["reservation_id"])
        state = json.loads((review / "review-state.json").read_text(encoding="utf-8"))
        dispatch = state["phases"]["post"]["rounds"]["1"]["dispatch"]["reviewer-one"]
        result = state["phases"]["post"]["rounds"]["1"]["results"]["reviewer-one"]
        self.assertEqual("delegation-budget-v1", dispatch["budget_accounting_owner"])
        self.assertEqual("parent-verified", result["delegation_attribution"])
        self.assertEqual(2, read_budget(self.ledger)["usage"]["units"])

    def test_manifest_declares_task_scoped_budget_activation(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        budget = manifest["model_routing"]["delegation_budget"]
        self.assertEqual("task-scoped-explicit-ledger", budget["activation_mode"])
        self.assertEqual("CP_DELEGATION_BUDGET_REQUIRED=1", budget["required_mode_environment"])


if __name__ == "__main__":
    unittest.main()
