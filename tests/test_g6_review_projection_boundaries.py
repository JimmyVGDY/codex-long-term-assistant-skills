"""中文：验证根隔离、过期或不完整复审，以及多复审者冲突边界。

English: Root isolation, stale/incomplete review, and multi-reviewer conflict boundaries.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1 as budget
from cp_runtime.common import repo_snapshot
from cp_runtime.g6_review_receipt_v1 import _delivery_path, _receipt_dir, _report, ingest, project_delivery
from cp_runtime.routing_contract import ref
from tests.test_g6_budget_v1 import capability, facts


ROLE = "cp_review_functional_business"


class G6ReviewProjectionBoundaryTests(unittest.TestCase):
    def test_native_final_answer_phase_is_structurally_readable(self):
        report = {"status": "pass", "findings": [], "checked_scope": ["bounded"],
                  "unverified_items": [], "summary": "Scoped result"}
        event = {"type": "response_item", "payload": {"type": "message",
                 "role": "assistant", "phase": "final_answer",
                 "content": [{"type": "output_text", "text": json.dumps(report)}]}}
        parsed, reason = _report((json.dumps(event) + "\n").encode())
        self.assertEqual(reason, "REPORT_STRUCTURE_VERIFIED")
        self.assertEqual(parsed["status"], "pass")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "roots"
        self.base.mkdir()
        self.repo = Path(__file__).resolve().parents[1]
        self.baseline = repo_snapshot(self.repo)["sha256"]

    def root(self, name, items):
        path = self.base / (name + ".jsonl")
        slots = [{"work_item_id": item, "allowed_profiles": ["g6-sol-medium"],
                  "baseline_profile": "g6-sol-medium", "review_phase": "post_review"}
                 for item in items]
        budget.initialize(path, identity_value=facts()["identity"],
                          host_session_id=name, repo_path=self.repo, task_id="task-a",
                          authorization_ref=ref("trusted-review-plan"), required_slots=slots)
        return path

    def reviewed(self, path, *, name, item, status="pass", findings=None, phase="post_review"):
        if phase != "post_review":
            # 中文：该辅助函数仅用于根中已经冻结的显式槽阶段。
            # English: This helper is used only for explicit slot phases already frozen in the root.
            state = budget.read_budget(path)
            slot = next(slot for slot in state["root"]["required_slots"] if slot["work_item_id"] == item)
            self.assertEqual(slot["review_phase"], phase)
        fact = facts(item)
        fact["baseline_sha256"] = self.baseline
        prepared = budget.prepare(path, facts=fact, capability=capability(), gates=[],
                                  agent_type=ROLE, task_name=name, message="Bounded review.",
                                  decision_time="2026-10-09T08:00:00Z")
        budget.approve_and_reserve(path, permit_id=prepared["permit_id"],
                                   host_call_id=name + "-call", session_id=path.stem,
                                   cwd=self.repo, args=prepared["decision"]["exact_tool_parameters"],
                                   now="2026-10-09T08:01:00Z")
        task_path = "/root/" + name
        budget.record_receipt(path, host_call_id=name + "-call", disposition="created",
                              agent_path=task_path, proof_ref=ref(name + "-created"))
        budget.record_terminal(path, agent_path=task_path, outcome="PASS",
                               proof_ref=ref(name + "-native-terminal"))
        report = {"status": status, "findings": findings or [],
                  "checked_scope": ["bounded fixture"], "unverified_items": [],
                  "summary": "Scoped report"}
        raw = (json.dumps({"type": "response_item", "payload": {"type": "message",
                            "role": "assistant", "phase": "final",
                            "content": [{"type": "output_text", "text": json.dumps(report)}]}})
               + "\n").encode()
        return ingest(path, raw_transcript=raw, task_path=task_path)

    def test_second_root_receipt_cannot_break_or_overwrite_first(self):
        first = self.root("root-one", ["item-one"])
        second = self.root("root-two", ["item-two"])
        self.reviewed(first, name="review_one", item="item-one")
        self.reviewed(second, name="review_two", item="item-two")
        one = project_delivery(first)
        two = project_delivery(second)
        self.assertEqual(one["review_receipt_count"], 1)
        self.assertEqual(two["review_receipt_count"], 1)
        self.assertTrue(one["independent_review_verified"])
        self.assertTrue(two["independent_review_verified"])
        self.assertNotEqual(_receipt_dir(first), _receipt_dir(second))
        self.assertNotEqual(_delivery_path(first), _delivery_path(second))
        self.assertTrue(_delivery_path(first).is_file())
        self.assertTrue(_delivery_path(second).is_file())

    def test_incomplete_and_mixed_blocking_reports_never_project_pass(self):
        incomplete = self.root("root-incomplete", ["item-one"])
        receipt = self.reviewed(incomplete, name="review_incomplete", item="item-one",
                                status="incomplete")
        self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
        self.assertFalse(project_delivery(incomplete)["independent_review_verified"])
        mixed = self.root("root-mixed", ["item-a", "item-b"])
        blocking = [{"id": "issue-a", "summary": "Scoped blocking concern"}]
        self.reviewed(mixed, name="review_blocking", item="item-a",
                      status="blocking", findings=blocking)
        self.reviewed(mixed, name="review_pass", item="item-b")
        projected = project_delivery(mixed)
        self.assertFalse(projected["independent_review_verified"])
        self.assertTrue(projected["unadjudicated_blocking_report"])
        self.assertTrue(projected["unresolved_review_conflict"])
        self.assertEqual(projected["review_receipt_count"], 2)
        self.assertEqual({row["status"] for row in projected["review_report_statuses"]["post_review"]},
                         {"blocking", "pass"})

    def test_unknown_phase_does_not_count_as_post_review(self):
        path = self.base / "root-unknown.jsonl"
        budget.initialize(path, identity_value=facts()["identity"],
                          host_session_id="root-unknown", repo_path=self.repo,
                          task_id="task-a", authorization_ref=ref("unknown-plan"))
        receipt = self.reviewed(path, name="pre_review_example", item="item-a")
        self.assertEqual(receipt["review_phase"], "UNKNOWN")
        self.assertFalse(project_delivery(path)["independent_review_verified"])

    def test_old_baseline_report_is_not_current_review_pass(self):
        path = self.root("root-stale", ["item-one"])
        self.reviewed(path, name="review_stale", item="item-one")
        with mock.patch("cp_runtime.g6_review_receipt_v1.repo_snapshot",
                        return_value={"sha256": "f" * 64}):
            result = project_delivery(path)
        self.assertFalse(result["independent_review_verified"])
        self.assertFalse(result["review_report_statuses"]["post_review"][0]["baseline_current"])


if __name__ == "__main__":
    unittest.main()
