"""中文：隔离临时账本中的追加额度、并发消费与旧流水兼容。

English: Scoped grants, atomic spending and legacy replay in isolated temporary journals.
Native human provenance is tested separately; unit fixtures never touch a live root.
"""
import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cp_runtime import g6_allowance_contract as contract, g6_budget_v1 as budget
from cp_runtime.common import utc_now
from cp_runtime.routing_contract import RoutingError, ref
from tests.test_g6_budget_v1 import facts, capability


class AllowanceBudgetTests(unittest.TestCase):
    def test_scope_matches_whole_case_sensitive_components(self):
        self.assertTrue(contract.within_scope(["docs/a.md", "src/app/deep/file.py"], ["docs/a.md", "src/app"]))
        for path in ("docs/a.md/../b.md", "src//app/file.py", "src/.git/config"):
            with self.subTest(path=path), self.assertRaises(RoutingError):
                contract.within_scope([path], ["src"])
        for path in ("docs/b.md", "src/application/file.py", "src/App/file.py", "src"):
            with self.subTest(path=path):
                self.assertFalse(contract.within_scope([path], ["docs/a.md", "src/app"]))

    def test_maximum_scope_preserves_exact_and_nested_boundaries(self):
        allowed = [f"src/module-{index:03d}" for index in range(256)]
        self.assertTrue(contract.within_scope(allowed, allowed))
        nested = [path + "/nested/file.py" for path in allowed]
        self.assertTrue(contract.within_scope(nested, allowed))
        nested[-1] = "src/module-255-extra/file.py"
        self.assertFalse(contract.within_scope(nested, allowed))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "budget.jsonl"
        self.repo = Path(__file__).resolve().parents[1]
        self.session = "isolated-allowance-test"
        budget.initialize(self.path, identity_value=facts()["identity"],
                          host_session_id=self.session, repo_path=self.repo, task_id="task-a",
                          authorization_ref=ref("synthetic-base"))

    def prepare(self, item, name, role="worker", **kwargs):
        return budget.prepare(self.path, facts=facts(item), capability=capability(), gates=[],
                              agent_type=role, task_name=name, message="Bounded fixture review.",
                              decision_time=utc_now(), **kwargs)

    def reserve(self, prepared, call):
        return budget.approve_and_reserve(self.path, permit_id=prepared["permit_id"],
                                          host_call_id=call, session_id=self.session, cwd=self.repo,
                                          args=prepared["decision"]["exact_tool_parameters"], now=utc_now())

    def finish(self, prepared, call, outcome="PASS"):
        self.reserve(prepared, call)
        budget.record_receipt(self.path, host_call_id=call, disposition="created",
                              agent_path="/root/" + call, proof_ref=ref("created-" + call))
        budget.record_terminal(self.path, agent_path="/root/" + call, outcome=outcome,
                               proof_ref=ref("terminal-" + call))

    def exhaust(self):
        for n in range(4):
            self.finish(self.prepare("base-" + str(n), "base_" + str(n)), "base" + str(n))

    def work(self, phase="post_review", role="cp_review_security_access"):
        return budget.register_review_work(self.path, boundary_id="feature-a", phase=phase,
            agent_type=role, profile_id="g6-sol-medium", scope_paths=["src/app.py"],
            purpose="Review the bounded feature.")

    def quote(self, work, **kwargs):
        return budget.request_allowance(self.path, work_ids=[work["work_id"]], **kwargs)

    def fixture_authority(self, label="approval"):
        # 中文：这只是 reducer 单元夹具，不是产品授权入口或原生来源证明。
        # English: Reducer fixture only, never a product authorization entrypoint.
        return {"source": "native-user-response", "session_ref": ref(self.session),
                "turn_ref": ref("turn"), "message_ref": ref(label), "record_ref": ref("record"),
                "transcript_path": str(Path(self.temporary.name) / "synthetic.jsonl"),
                "transcript_path_ref": ref("path"), "transcript_file_ref": ref("file"),
                "header_ref": ref("header"), "start": 100, "end": 200, "authorized_at": utc_now()}

    def grant_fixture(self, quote, label="approval"):
        with budget.OwnerTokenLock(self.path, timeout=2):
            budget._append(self.path, budget._read_events(self.path), "ALLOWANCE_GRANTED",
                           {"request_id": quote["request_id"], "authorization": self.fixture_authority(label)})

    def test_v1_prefix_and_policy_are_unchanged(self):
        self.finish(self.prepare("old", "old_work"), "old")
        raw = self.path.read_bytes()
        events = budget._read_events(self.path)
        before = budget.replay(copy.deepcopy(events))
        self.work()
        self.assertTrue(self.path.read_bytes().startswith(raw))
        self.assertEqual(budget.replay(events), before)
        self.assertNotIn("protocol_version", before)
        self.assertEqual(budget.snapshot(before, work_item_id="other", depth=0)["schema_version"],
                         "g6-budget-snapshot/1")
        self.assertEqual(budget.read_budget(self.path)["root"], before["root"])
        self.assertEqual(budget._read_events(self.path)[-1]["schema_version"], contract.JOURNAL_SCHEMA)

    def test_grant_restores_review_without_rewriting_base_spend(self):
        self.exhaust()
        work = self.work()
        quote = self.quote(work)
        denied = self.prepare(work["work_id"], "before", work["agent_type"])
        self.assertIsNone(denied["permit_id"])
        self.grant_fixture(quote)
        prepared = self.prepare(work["work_id"], "after", work["agent_type"])
        self.assertEqual(prepared["decision"]["approved_profile"], "g6-sol-medium")
        self.finish(prepared, "after")
        state = budget.read_budget(self.path)
        self.assertEqual(budget.snapshot(state, work_item_id="status", depth=0)["completed_charged_units"], 16)
        status = budget.allowance_status(state)
        self.assertEqual(status["total_usage"]["completed_charged_units"], 20)
        self.assertEqual(status["grants"][0]["usage"]["completed_charged_units"], 4)
        self.assertIsNone(self.prepare(work["work_id"], "extra", work["agent_type"])["permit_id"])

    def test_worker_and_other_reviewer_cannot_spend_grant(self):
        self.exhaust()
        work = self.work()
        self.grant_fixture(self.quote(work))
        self.assertIsNone(self.prepare("unrelated", "worker")["permit_id"])
        for role in ["worker", "explorer", "cp_review_data_contract"]:
            with self.subTest(role=role), self.assertRaises(RoutingError):
                self.prepare(work["work_id"], "wrong_" + role, role)
        denied = self.prepare(work["work_id"], "wrong_profile", work["agent_type"],
                              explicit_user_profile="g6-astra-high")
        self.assertIsNone(denied["permit_id"])

    def test_concurrent_prepared_calls_cannot_double_spend_one_grant(self):
        self.exhaust()
        work = self.work()
        self.grant_fixture(self.quote(work))
        prepared = [self.prepare(work["work_id"], "race_" + str(n), work["agent_type"]) for n in range(2)]
        def run(n):
            try:
                self.reserve(prepared[n], "race" + str(n))
                return "reserved"
            except RoutingError:
                return "denied"
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(run, range(2))), ["denied", "reserved"])
        state = budget.read_budget(self.path)
        self.assertEqual(budget.allowance_status(state)["grants"][0]["usage"]["inflight_reserved_units"], 4)

    def test_pending_quote_is_idempotent_and_authority_is_not_reusable(self):
        work = self.work()
        quote = self.quote(work)
        original = self.path.read_bytes()
        self.assertEqual(self.quote(work), quote)
        self.assertEqual(self.path.read_bytes(), original)
        self.grant_fixture(quote)
        second = self.quote(work)
        before = self.path.read_bytes()
        with self.assertRaises(RoutingError):
            self.grant_fixture(second)
        self.assertEqual(self.path.read_bytes(), before)

    def test_no_start_releases_grant_units_but_retry_attempts_are_finite(self):
        self.exhaust()
        work = self.work()
        self.grant_fixture(self.quote(work))
        for n in range(3):
            prepared = self.prepare(work["work_id"], "no_start_" + str(n), work["agent_type"])
            call = "no-start-" + str(n)
            self.reserve(prepared, call)
            budget.record_receipt(self.path, host_call_id=call, disposition="not_started",
                                  agent_path=None, proof_ref=ref(call))
        self.assertIsNone(self.prepare(work["work_id"], "retry_four", work["agent_type"])["permit_id"])
        usage = budget.allowance_status(budget.read_budget(self.path))["grants"][0]["usage"]
        self.assertEqual(usage["completed_charged_units"], 0)
        self.assertEqual(usage["completed_charged_attempts"], 3)

    def test_running_or_unknown_attempt_cannot_be_restarted(self):
        self.exhaust()
        work = self.work()
        self.grant_fixture(self.quote(work))
        self.reserve(self.prepare(work["work_id"], "unknown", work["agent_type"]), "unknown")
        with self.assertRaisesRegex(RoutingError, "ALREADY_INFLIGHT"):
            self.prepare(work["work_id"], "duplicate", work["agent_type"])

    def test_two_prepared_calls_cannot_run_same_work_even_with_two_granted_runs(self):
        self.exhaust()
        work = self.work()
        self.grant_fixture(self.quote(work, dispatches=2))
        first = self.prepare(work["work_id"], "first", work["agent_type"])
        second = self.prepare(work["work_id"], "second", work["agent_type"])
        self.reserve(first, "first")
        with self.assertRaisesRegex(RoutingError, "ALREADY_INFLIGHT"):
            self.reserve(second, "second")

    def test_required_hold_returns_after_confirmed_no_start(self):
        work = self.work()
        prepared = self.prepare(work["work_id"], "no_start", work["agent_type"])
        self.reserve(prepared, "no_start")
        budget.record_receipt(self.path, host_call_id="no_start", disposition="not_started",
                              agent_path=None, proof_ref=ref("not-created"))
        view = budget.snapshot(budget.read_budget(self.path), work_item_id="other", depth=0)
        self.assertEqual(view["future_required_hold_units"], 4)
        self.assertEqual(view["future_required_hold_attempts"], 1)

    def test_declared_work_profile_does_not_authorize_automatic_highest_cost(self):
        work = budget.register_review_work(self.path, boundary_id="high-cost", phase="post_review",
            agent_type="cp_review_security_access", profile_id="g6-astra-high", scope_paths=["src/app.py"],
            purpose="Review a declared high-cost requirement.")
        denied = self.prepare(work["work_id"], "unapproved_high", work["agent_type"])
        self.assertIsNone(denied["permit_id"])
        self.grant_fixture(self.quote(work))
        prepared = self.prepare(work["work_id"], "authorized_high", work["agent_type"])
        self.assertEqual(prepared["decision"]["approved_profile"], "g6-astra-high")
        self.reserve(prepared, "authorized_high")
        self.assertFalse(budget.read_budget(self.path)["permits"][prepared["permit_id"]]["upward_adjustment"])

    def test_registered_work_reserves_required_review_and_repair(self):
        first, repair = self.work(), self.work("repair_review")
        view = budget.snapshot(budget.read_budget(self.path), work_item_id="worker", depth=0)
        self.assertEqual(view["future_required_hold_units"], 8)
        self.finish(self.prepare(first["work_id"], "first", first["agent_type"]), "first")
        view = budget.snapshot(budget.read_budget(self.path), work_item_id="worker", depth=0)
        self.assertEqual(view["future_required_hold_units"], 4)
        self.assertEqual(self.work("repair_review")["work_id"], repair["work_id"])

    def test_old_prepared_permit_survives_additive_protocol_transition(self):
        prepared = self.prepare("old", "old")
        self.work()
        self.reserve(prepared, "old")
        state = budget.read_budget(self.path)
        self.assertEqual(state["reservations"][prepared["permit_id"]]["funding_id"], "base")

    def test_revocation_blocks_new_spend_but_preserves_active_accounting(self):
        self.exhaust()
        work = self.work()
        quote = self.quote(work, dispatches=2)
        self.grant_fixture(quote)
        prepared = self.prepare(work["work_id"], "active", work["agent_type"])
        self.reserve(prepared, "active")
        with budget.OwnerTokenLock(self.path, timeout=2):
            budget._append(self.path, budget._read_events(self.path), "ALLOWANCE_REVOKED",
                           {"request_id": quote["request_id"], "authorization": self.fixture_authority("revoke")})
        budget.record_receipt(self.path, host_call_id="active", disposition="created",
                              agent_path="/root/active", proof_ref=ref("created"))
        budget.record_terminal(self.path, agent_path="/root/active", outcome="PASS", proof_ref=ref("done"))
        self.assertIsNone(self.prepare(work["work_id"], "revoked", work["agent_type"])["permit_id"])
        self.assertEqual(budget.allowance_status(budget.read_budget(self.path))["total_usage"]["completed_charged_units"], 20)

    def test_scope_refresh_does_not_include_sibling_or_parent_paths(self):
        self.assertTrue(contract.within_scope(["src/app.py"], ["src"]))
        self.assertFalse(contract.within_scope(["src-other/app.py"], ["src"]))

    def test_reinstatement_preserves_spend_and_rejects_stale_decision(self):
        self.exhaust()
        work = self.work()
        quote = self.quote(work, dispatches=2)
        self.grant_fixture(quote)
        self.finish(self.prepare(work["work_id"], "before_revoke", work["agent_type"]), "before_revoke")
        revoke = {"request_id": quote["request_id"], "authorization": self.fixture_authority("decline")}
        revoke["authorization"].update(start=200, end=300)
        with budget.OwnerTokenLock(self.path, timeout=2):
            budget._append(self.path, budget._read_events(self.path), "ALLOWANCE_REVOKED", revoke)
        proof = self.fixture_authority("restore")
        stale = {"request_id": quote["request_id"], "authorization": proof, "previous_decision_ref": ref(revoke)}
        with self.assertRaisesRegex(RoutingError, "DECISION_NOT_LATER"):
            budget._append(self.path, budget._read_events(self.path), "ALLOWANCE_REINSTATED", stale)
        proof.update(start=300, end=400)
        with budget.OwnerTokenLock(self.path, timeout=2):
            budget._append(self.path, budget._read_events(self.path), "ALLOWANCE_REINSTATED", stale)
        state = budget.read_budget(self.path)
        status = budget.allowance_status(state)
        self.assertEqual(len(status["grants"]), 1)
        self.assertEqual(status["grants"][0]["usage"]["completed_charged_units"], 4)
        self.finish(self.prepare(work["work_id"], "after_restore", work["agent_type"]), "after_restore")
        self.assertIsNone(self.prepare(work["work_id"], "no_refund", work["agent_type"])["permit_id"])
        self.assertFalse(contract.within_scope(["src"], ["src/app.py"]))
        for path in ["../secret", "/absolute", "C:/absolute", "src/../secret", ".git/config"]:
            with self.subTest(path=path), self.assertRaises(RoutingError):
                contract.scope_paths([path])


if __name__ == "__main__":
    unittest.main()
