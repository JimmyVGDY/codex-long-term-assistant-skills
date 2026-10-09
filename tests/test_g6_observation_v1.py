"""中文：验证自然观察保留未知、失败消耗、根隔离和重复尝试口径。

English: Natural observations retain unknowns, failed cost, root isolation, and retry denominators.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cp_runtime import g6_budget_v1 as budget
from cp_runtime.g6_observation_v1 import collect
from cp_runtime.g6_review_receipt_v1 import project_delivery
from cp_runtime.routing_contract import ref
from tests.test_g6_budget_v1 import capability, facts


class G6ObservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "root.jsonl"
        self.repo = Path(__file__).resolve().parents[1]
        budget.initialize(self.path, identity_value=facts()["identity"], task_id="task-a",
                          host_session_id="observation-session", repo_path=self.repo,
                          authorization_ref=ref("authorized"))

    def attempt(self, number, disposition="created", outcome=None):
        name = "observation_" + str(number)
        prepared = budget.prepare(self.path, facts=facts(), capability=capability(), gates=[],
            agent_type="worker", task_name=name, message="private prompt must not be exported",
            decision_time="2026-10-09T08:00:00Z")
        budget.approve_and_reserve(self.path, permit_id=prepared["permit_id"], host_call_id=name,
            session_id="observation-session", cwd=self.repo,
            args=prepared["decision"]["exact_tool_parameters"], now="2026-10-09T08:01:00Z")
        agent = "/root/" + name if disposition == "created" else None
        budget.record_receipt(self.path, host_call_id=name, disposition=disposition,
                              agent_path=agent, proof_ref=ref(name))
        if outcome is not None:
            budget.record_terminal(self.path, agent_path=agent, outcome=outcome, proof_ref=ref(outcome))

    def observe(self):
        return collect(self.path, expected_head=budget.read_budget(self.path)["head_hash"])

    def test_failed_unknown_and_unstarted_attempts_do_not_invent_success_or_free_cost(self):
        self.attempt(1, outcome="FAILED")
        self.attempt(2, disposition="not_started")
        self.attempt(3, outcome="UNKNOWN")
        value = self.observe()
        row = value["groups"][0]
        self.assertEqual(row["reserved_attempts"], 3)
        self.assertEqual(row["distinct_work_items"], 1)
        self.assertEqual(row["charged_planning_units"], 8)
        self.assertEqual(row["native_outcomes"], {"FAILED": 1, "UNKNOWN": 1})
        self.assertIsNone(value["business_completion_rate"])
        self.assertIsNone(value["actual_credits"])
        self.assertEqual(value["identity"], facts()["identity"])
        self.assertNotIn("private prompt", json.dumps(value))

    def test_empty_and_running_roots_have_no_fabricated_latency(self):
        self.assertEqual(self.observe()["groups"], [])
        self.attempt(1)
        row = self.observe()["groups"][0]
        self.assertEqual(row["unresolved_attempts"], 1)
        self.assertEqual(row["inflight_planning_units"], 4)
        self.assertIsNone(row["reservation_to_terminal_ms"]["p95"])

    def test_changed_head_is_stale_and_stop_projection_really_consumes_observation(self):
        head = budget.read_budget(self.path)["head_hash"]
        self.attempt(1, outcome="PASS")
        self.assertEqual(collect(self.path, expected_head=head)["status"], "STALE_SNAPSHOT")
        projected = project_delivery(self.path)
        self.assertEqual(projected["observation"]["status"], "OBSERVED")
        self.assertIsNone(projected["observation"]["business_completion_rate"])
        with patch("cp_runtime.g6_observation_v1.collect", side_effect=OSError("unavailable")):
            degraded = project_delivery(self.path)
        self.assertEqual(degraded["observation"]["status"], "UNAVAILABLE")
        self.assertEqual(degraded["next_action"], projected["next_action"])
