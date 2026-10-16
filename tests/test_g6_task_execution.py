"""中文：执行追加的角色隔离、历史兼容与最坏容量；不使用真实账户。
English: Execution grants, role separation, legacy replay and worst-case capacity in isolated fixtures.
"""
import copy
import unittest
from unittest import mock

from cp_runtime import g6_allowance_contract as contract, g6_budget_v1 as budget
from cp_runtime import g6_journal_capacity as capacity
from cp_runtime.common import canonical_json, utc_now
from cp_runtime.routing_contract import ref
from tests import test_g6_allowance_budget as fixtures


class TaskExecutionBudgetTests(unittest.TestCase):
    setUp = fixtures.AllowanceBudgetTests.setUp
    prepare = fixtures.AllowanceBudgetTests.prepare
    reserve = fixtures.AllowanceBudgetTests.reserve
    finish = fixtures.AllowanceBudgetTests.finish
    exhaust = fixtures.AllowanceBudgetTests.exhaust
    quote = fixtures.AllowanceBudgetTests.quote
    fixture_authority = fixtures.AllowanceBudgetTests.fixture_authority
    grant_fixture = fixtures.AllowanceBudgetTests.grant_fixture

    def work(self, role="explorer", profile="g6-sol-medium", purpose="Execute bounded public fixtures."):
        return budget.register_review_work(self.path, boundary_id="task-a", phase="task_execution",
            agent_type=role, profile_id=profile, scope_paths=["tests"], purpose=purpose)

    def test_old_review_question_and_prefix_survive_execution_upgrade(self):
        old = fixtures.AllowanceBudgetTests.work(self)
        quote = self.quote(old)
        question = contract.quote_question(quote, budget.read_budget(self.path)["review_work"])
        prefix = self.path.read_bytes()
        state = budget.read_budget(self.path)
        self.work()
        self.assertTrue(self.path.read_bytes().startswith(prefix))
        current = budget.read_budget(self.path)
        self.assertEqual(current["protocol_version"], 3)
        self.assertEqual(contract.quote_question(quote, current["review_work"]), question)
        self.assertEqual(state["root"], current["root"])
        self.assertEqual(current["allowance_requests"][quote["request_id"]], quote)

    def test_execution_quote_and_grant_cannot_fund_review_or_other_role(self):
        self.exhaust()
        work = self.work()
        quote = self.quote(work, dispatches=10)
        self.assertEqual(quote["question_version"], 2)
        words = contract.quote_question(quote, budget.read_budget(self.path)["review_work"])
        self.assertIn("explorer / g6-sol-medium：10 次调用、30 次尝试", words)
        self.assertIsNone(self.prepare(work["work_id"], "before", "explorer")["permit_id"])
        self.grant_fixture(quote)
        for role in ("worker", "cp_review_security_access"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.prepare(work["work_id"], "wrong_" + role, role)
        created = self.prepare(work["work_id"], "bounded", "explorer")
        self.finish(created, "bounded", outcome="UNKNOWN")
        current = budget.read_budget(self.path)
        self.assertEqual(budget.allowance_status(current)["total_usage"]["completed_charged_units"], 20)
        self.assertEqual(budget.snapshot(current, work_item_id="status", depth=0)["completed_charged_units"], 16)

    def test_mixed_quote_and_reviewer_execution_role_are_rejected_without_writes(self):
        worker = self.work("worker")
        reviewer = fixtures.AllowanceBudgetTests.work(self)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "ROLE_PHASE_MIXED"):
            budget.request_allowance(self.path, work_ids=[worker["work_id"], reviewer["work_id"]])
        with self.assertRaises(ValueError):
            self.work("cp_review_security_access")
        self.assertEqual(self.path.read_bytes(), before)

    def test_112_call_quote_holds_worst_case_capacity_and_large_requote_fails_before_write(self):
        self.exhaust()
        sol = self.work()
        luna = self.work("explorer", "g6-luna-low", "Route public synthetic prompts.")
        quote = budget.request_allowance(self.path, work_ids=[sol["work_id"], luna["work_id"]],
            dispatches={sol["work_id"]: 32, luna["work_id"]: 80})
        self.assertEqual(sum(row["attempts"] for row in quote["allocations"]), 336)
        view = capacity.require_room(budget.read_budget(self.path), self.path.stat().st_size)
        self.assertGreaterEqual(view["reserved_future_records"], 336 * 6)
        before = self.path.read_bytes()
        with mock.patch.object(capacity, "MAX_RECORDS", view["stored_records"] + view["reserved_future_records"] + 2):
            with self.assertRaisesRegex(ValueError, "CAPACITY_INSUFFICIENT"):
                self.quote(sol, dispatches=2)
        self.assertEqual(self.path.read_bytes(), before)
        with mock.patch.object(capacity, "MAX_BYTES", view["stored_bytes"] + view["reserved_future_bytes"] + 1):
            with self.assertRaisesRegex(ValueError, "CAPACITY_INSUFFICIENT"):
                self.quote(sol, dispatches=2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_336_no_start_attempts_replay_beyond_legacy_limit_without_charge_reset(self):
        self.exhaust()
        work = self.work()
        quote = self.quote(work, dispatches=112)
        self.grant_fixture(quote)
        self.prepare(work["work_id"], "template", "explorer")
        events = budget._read_events(self.path)
        template = copy.deepcopy(events.pop()["data"])
        funding = contract.funding_id(quote["request_id"], work["work_id"])
        for number in range(336):
            pid = "G6P_" + f"{number:032x}"
            permit = {**template, "permit_id": pid, "task_name": "attempt_" + str(number)}
            for kind, data in (
                    ("PREPARED", permit),
                    ("RESERVED", {"permit_id": pid, "host_call_ref": ref(number),
                                  "reserved_at": utc_now(), "funding_id": funding}),
                    ("HOST_RECEIPT", {"permit_id": pid, "disposition": "not_started",
                                      "agent_ref": None, "proof_ref": ref(["no-start", number])})):
                events.append(budget._event(events[-1], kind, data))
        self.path.write_text("\n".join(canonical_json(row) for row in events) + "\n", encoding="utf-8")
        self.assertGreater(len(events), budget.MAX_RECORDS)
        state = budget.read_budget(self.path)
        usage = budget.allowance_status(state)
        self.assertEqual(usage["total_usage"]["completed_charged_units"], 16)
        self.assertEqual(usage["grants"][0]["usage"]["completed_charged_attempts"], 336)
        self.assertIsNone(self.prepare(work["work_id"], "over_limit", "explorer")["permit_id"])
        capacity.require_room(state, self.path.stat().st_size)

    def test_v3_cannot_be_downgraded_or_hidden_in_v2_event(self):
        self.work()
        events = budget._read_events(self.path)
        bad = copy.deepcopy(events[-1])
        bad["schema_version"] = contract.JOURNAL_SCHEMA
        bad["record_hash"] = ref({key: value for key, value in bad.items() if key != "record_hash"})[7:]
        with self.assertRaisesRegex(ValueError, "TASK_EXECUTION_VERSION_REQUIRED"):
            budget.replay([*events[:-1], bad])
        close = budget._event(events[-1], "REVIEW_WORK_CLOSED", {"work_id": events[-1]["data"]["work_id"]})
        close["schema_version"] = contract.JOURNAL_SCHEMA
        close["record_hash"] = ref({key: value for key, value in close.items() if key != "record_hash"})[7:]
        with self.assertRaisesRegex(ValueError, "LEDGER_CHAIN"):
            budget.replay([*events, close])


if __name__ == "__main__":
    unittest.main()
