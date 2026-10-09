"""中文：重试计算真实尝试，并保留终态未知的在途调用。

English: Retries count real attempts and preserve unknown in-flight calls.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cp_runtime import g6_budget_v1 as budget
from cp_runtime.g6_retry_v1 import next_action
from cp_runtime.routing_contract import ref

from tests.test_g6_budget_v1 import capability, facts


class G6RetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "budget.jsonl"
        self.repo = Path(__file__).resolve().parents[1]
        budget.initialize(self.path, identity_value=facts()["identity"],
                          host_session_id="retry-session", repo_path=self.repo,
                          task_id="task-a", authorization_ref=ref("authorized"))

    def attempt(self, number: int, complete: bool = True):
        name = f"retry_agent_{number}"
        result = budget.prepare(self.path, facts=facts(), capability=capability(), gates=[],
                                agent_type="worker", task_name=name, message=f"Attempt {number}",
                                decision_time="2026-10-09T08:00:00Z")
        budget.approve_and_reserve(self.path, permit_id=result["permit_id"],
                                   host_call_id=f"retry-call-{number}", session_id="retry-session",
                                   cwd=self.repo, args=result["decision"]["exact_tool_parameters"],
                                   now="2026-10-09T08:01:00Z")
        if complete:
            budget.record_receipt(self.path, host_call_id=f"retry-call-{number}",
                                  disposition="created", agent_path=f"/root/{name}",
                                  proof_ref=ref(f"created-{number}"))
            budget.record_terminal(self.path, agent_path=f"/root/{name}", outcome="FAILED",
                                   proof_ref=ref(f"failed-{number}"))

    def advice(self, kind="host_capacity", **extra):
        return next_action(budget.read_budget(self.path), work_item_id="item-a",
                           failure_kind=kind, now="2026-10-09T08:02:00Z",
                           deadline_at="2026-10-09T08:10:00Z", **extra)

    def test_running_unknown_reuses_same_handle(self):
        self.attempt(1, complete=False)
        answer = self.advice()
        self.assertEqual(answer["action"], "RESUME_SAME_HANDLE")
        self.assertIsNotNone(answer["same_handle_ref"])

    def test_transient_retry_has_bounded_backoff_and_attempt_limit(self):
        self.attempt(1)
        self.assertEqual(self.advice()["action"], "RETRY_NEW_PERMIT")
        self.assertEqual(self.advice(host_retry_after_ms=2500)["wait_ms"], 2500)
        self.attempt(2)
        self.assertEqual(self.advice()["action"], "RETRY_NEW_PERMIT")
        self.attempt(3)
        self.assertEqual(self.advice()["reason_code"], "TRANSIENT_RETRY_LIMIT")

    def test_quality_without_changed_input_and_hard_failure_do_not_retry(self):
        self.attempt(1)
        self.assertEqual(self.advice("quality")["action"], "CONTINUE_LOCAL")
        self.assertEqual(self.advice("quality", changed_input_ref=ref("new-input"))["action"],
                         "REPREPARE_WITH_CHANGED_INPUT")
        self.assertEqual(self.advice("authorization")["action"], "STOP_AFFECTED_ACTION")

    def test_deadline_bounds_transient_retry(self):
        self.attempt(1)
        answer = next_action(budget.read_budget(self.path), work_item_id="item-a",
                             failure_kind="transport_interruption", now="2026-10-09T08:02:00Z",
                             deadline_at="2026-10-09T08:02:00Z")
        self.assertEqual(answer["reason_code"], "RETRY_DEADLINE_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
