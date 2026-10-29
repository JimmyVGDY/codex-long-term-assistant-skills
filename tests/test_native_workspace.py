"""中文：原生目录记录仅为证据，不修改授权和预算。
English: Native workspace records are evidence, not authorization or budget changes.
"""
import copy
import json
import unittest
from unittest import mock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cp_runtime import native_workspace as workspace
from cp_runtime import g6_task_origin as origin, g6_task_scope as scope, g6_handoff_v1 as legacy
from cp_runtime import g6_allowance_authority as authority, g6_budget_v1 as budget
from cp_runtime.common import atomic_write_json
from cp_runtime.routing_contract import ref
from cp_runtime.g6_allowance_authority import _native_header
import test_g6_task_scope as fixtures
import test_g6_task_source_recovery as recovery_fixtures


class NativeWorkspaceTests(unittest.TestCase):
    setUp = fixtures.TaskScopeTests.setUp
    parent = fixtures.TaskScopeTests.parent
    emit = fixtures.TaskScopeTests.emit

    def moved(self):
        target = self.base / "selected-project"
        target.mkdir()
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(target)})
        return target

    def test_current_turn_proves_workspace_without_weakening_allowance_header(self):
        target = self.moved()
        before = self.transcript.read_bytes()
        proof = workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)
        workspace.verify(self.transcript, proof, session_id=self.session, cwd=target)
        self.assertEqual(before, self.transcript.read_bytes())
        with self.assertRaisesRegex(ValueError, "G6_ALLOWANCE_NATIVE_SOURCE_IDENTITY"):
            _native_header(self.transcript, session_id=self.session, cwd=target)

    def test_message_text_cannot_supply_workspace_context(self):
        self.emit("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": json.dumps({"turn_id": self.turn, "cwd": str(self.repo)})}]})
        with self.assertRaisesRegex(ValueError, "WORKSPACE_CONTEXT_UNAVAILABLE"):
            workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=self.repo)

    def test_other_turn_and_foreign_project_are_rejected(self):
        target = self.moved()
        with self.assertRaisesRegex(ValueError, "WORKSPACE_CONTEXT_UNAVAILABLE"):
            workspace.observe(self.transcript, session_id=self.session, turn_id="other", cwd=target)
        with self.assertRaisesRegex(ValueError, "WORKSPACE_CONTEXT_IDENTITY"):
            workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=self.repo)

    def test_same_turn_with_conflicting_directories_is_rejected(self):
        target = self.moved()
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(self.repo)})
        with self.assertRaisesRegex(ValueError, "WORKSPACE_CONTEXT_IDENTITY"):
            workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)

    def test_changed_native_context_cannot_be_replayed(self):
        target = self.moved()
        proof = workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)
        with self.transcript.open("r+b") as stream:
            stream.seek(proof["start"])
            stream.write(b" ")
        with self.assertRaisesRegex(ValueError, "WORKSPACE_CONTEXT_CHANGED"):
            workspace.verify(self.transcript, proof, session_id=self.session, cwd=target)

    def test_identical_replacement_is_not_the_original_file(self):
        target = self.moved()
        proof = workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)
        replacement = self.transcript.with_suffix(".replacement")
        replacement.write_bytes(self.transcript.read_bytes())
        replacement.replace(self.transcript)
        with self.assertRaisesRegex(ValueError, "WORKSPACE_SOURCE_REPLACED"):
            workspace.verify(self.transcript, proof, session_id=self.session, cwd=target)

    def test_proof_bounds_and_identity_are_rechecked(self):
        target = self.moved()
        proof = workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)
        for key, value in (("session_ref", "sha256:" + "0" * 64), ("start", -1), ("end", True),
                           ("record_ref", "invalid"), ("repo_path", str(self.repo))):
            forged = copy.deepcopy(proof)
            forged[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                workspace.verify(self.transcript, forged, session_id=self.session, cwd=target)

    def test_malformed_native_header_has_a_contract_error(self):
        for value in ([], {"type": "session_meta", "payload": []}):
            self.transcript.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "NATIVE_SOURCE_IDENTITY"):
                workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=self.repo)

    def test_context_before_large_tool_records_is_read_with_bounded_windows(self):
        target = self.moved()
        for _ in range(3):
            self.emit("event_msg", {"type": "tool_output", "data": "x" * 1_100_000})
        with mock.patch.object(workspace, "complete_window", wraps=workspace.complete_window) as read:
            proof = workspace.observe(self.transcript, session_id=self.session, turn_id=self.turn, cwd=target)
        self.assertGreater(read.call_count, 1)
        self.assertLessEqual(read.call_count, workspace.MAX_CONTEXT_WINDOWS)
        workspace.verify(self.transcript, proof, session_id=self.session, cwd=target)


class WorkspaceSourceRecoveryTests(unittest.TestCase):
    setUp = fixtures.TaskScopeTests.setUp
    parent = fixtures.TaskScopeTests.parent
    emit = fixtures.TaskScopeTests.emit
    observe_parent = recovery_fixtures.NativeSourceRecoveryTests.observe_parent
    native_user = recovery_fixtures.NativeSourceRecoveryTests.native_user

    def change_workspace(self):
        self.repo = self.base / "selected-project"
        self.repo.mkdir()
        self.turn = "selected-project-turn"
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(self.repo)})

    def test_first_project_selection_preserves_old_source_and_creates_no_implicit_budget(self):
        origin.observe({"session_id": self.session, "cwd": str(self.repo),
                        "transcript_path": str(self.transcript), "hook_event_name": "UserPromptSubmit"})
        old_path = origin._directory(self.session) / "source.json"
        old = old_path.read_bytes()
        self.change_workspace()
        self.native_user()
        self.assertFalse(legacy.pointer_for(self.session).exists())
        prepared = origin.prepare(self.session, self.repo)
        self.assertEqual(1, len(prepared["origins"]))
        row = prepared["origins"][0]
        frozen = origin.read_origin(self.session, self.repo, row["origin_ref"])
        self.assertEqual("g6-native-task-origin/2", frozen["schema_version"])
        selected = scope.select(session=self.session, cwd=self.repo, task_id="workspace-selection",
                                origin_ref=row["origin_ref"], relation="independent")
        before = Path(selected["new_ledger_path"]).read_bytes()
        with mock.patch("cp_runtime.g6_budget_v1.read_budget", side_effect=AssertionError("source observation replayed budget")):
            self.observe_parent()
        origin.read_origin(self.session, self.repo, row["origin_ref"])
        self.assertEqual(before, Path(selected["new_ledger_path"]).read_bytes())
        self.assertEqual(old, old_path.read_bytes())

    def test_existing_root_cannot_be_moved_by_new_turn_context(self):
        self.native_user()
        row = origin.prepare(self.session, self.repo)["origins"][0]
        selected = scope.select(session=self.session, cwd=self.repo, task_id="original-task",
                                origin_ref=row["origin_ref"], relation="independent")
        ledger = Path(selected["new_ledger_path"])
        before = ledger.read_bytes()
        self.change_workspace()
        with self.assertRaisesRegex(ValueError, "TASK_WORKSPACE_BOUND_ROOT"):
            self.native_user()
        self.assertEqual(before, ledger.read_bytes())

    def test_caller_path_does_not_establish_workspace_source(self):
        self.change_workspace()
        self.native_user(observed=False)
        with self.assertRaises(ValueError):
            origin.recover_source(self.session, self.repo, self.transcript)
        self.assertFalse((origin._directory(self.session, self.repo) / "source.json").exists())

    def test_repeated_concurrent_locators_do_not_create_budgets(self):
        self.change_workspace()
        self.native_user(observed=False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: self.observe_parent(), range(8)))
        self.assertTrue(all(row["schema_version"] == "g6-task-native-locator/2" for row in values))
        self.assertFalse(legacy.pointer_for(self.session).exists())
        self.assertEqual(1, len(origin.prepare(self.session, self.repo)["origins"]))

    def test_later_native_turn_preserves_old_origin(self):
        self.change_workspace()
        self.native_user()
        first = origin.prepare(self.session, self.repo)["origins"][0]
        self.turn = "next-native-turn"
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(self.repo)})
        self.emit("response_item", {"type": "message", "role": "user", "id": "next-user",
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": ["user.text"]},
                  "content": [{"type": "input_text", "text": "A second goal in this project"}]})
        self.observe_parent()
        latest = origin.prepare(self.session, self.repo)["origins"]
        self.assertEqual(2, len(latest))
        self.assertIn(first["origin_ref"], [row["origin_ref"] for row in latest])
        self.assertNotEqual(first["origin_ref"], latest[-1]["origin_ref"])
        origin.read_origin(self.session, self.repo, first["origin_ref"])

    def test_unobserved_turn_cannot_be_selected_from_same_file(self):
        self.change_workspace()
        self.native_user()
        first = origin.prepare(self.session, self.repo)["origins"][0]
        self.turn = "unobserved-foreign-turn"
        self.emit("response_item", {"type": "message", "role": "user", "id": "foreign-user",
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": ["user.text"]},
                  "content": [{"type": "input_text", "text": "A foreign task"}]})
        result = origin.prepare(self.session, self.repo)
        self.assertEqual([first["origin_ref"]], [row["origin_ref"] for row in result["origins"]])

    def test_historical_human_goal_with_matching_native_context_is_recoverable(self):
        self.change_workspace()
        self.native_user()
        first_turn = self.turn
        self.turn = "automatic-continuation"
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(self.repo)})
        self.emit("response_item", {"type": "message", "role": "user", "id": "automatic-goal",
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": ["goal.internal_context"]},
                  "content": [{"type": "input_text", "text": "Continue the implementation"}]})
        self.observe_parent()
        view = origin.prepare(self.session, self.repo)
        self.assertEqual(1, len(view["origins"]))
        frozen = origin.read_origin(self.session, self.repo, view["origins"][0]["origin_ref"])
        self.assertEqual(first_turn, frozen["native_turn_id"])
        self.assertEqual(first_turn, frozen["workspace_proof"]["turn_id"])
        self.assertLessEqual(view["workspace_context_lookups"], view["workspace_context_lookup_limit"])

    def test_empty_workspace_directory_cannot_hide_an_orphan_root(self):
        initial = self.repo
        self.change_workspace()
        directory = origin._directory(self.session) / "workspaces" / ref(origin._identity(self.repo))[7:]
        directory.mkdir(parents=True)
        ledger = directory.parents[3] / "roots" / (ref(self.session)[7:] + ".jsonl")
        budget.initialize(ledger, identity_value=origin._identity(initial), host_session_id=self.session,
                          repo_path=initial, task_id="orphaned-original-task", authorization_ref=ref("fixture-root"))
        before = ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "TASK_WORKSPACE_BOUND_ROOT"):
            self.native_user()
        self.assertEqual(before, ledger.read_bytes())
        self.assertFalse((directory / "native-locator.json").exists())

    def test_broken_git_metadata_is_not_a_projectless_start(self):
        (self.repo / ".git").mkdir()
        self.change_workspace()
        with self.assertRaisesRegex(ValueError, "TASK_WORKSPACE_HANDOFF_REQUIRED"):
            self.native_user()


class WorkspaceAllowanceTests(unittest.TestCase):
    parent = fixtures.TaskScopeTests.parent
    emit = fixtures.TaskScopeTests.emit
    observe_parent = recovery_fixtures.NativeSourceRecoveryTests.observe_parent
    native_user = recovery_fixtures.NativeSourceRecoveryTests.native_user
    change_workspace = WorkspaceSourceRecoveryTests.change_workspace

    def setUp(self):
        fixtures.TaskScopeTests.setUp(self)
        self.initial = self.repo
        self.change_workspace()
        self.native_user()
        item = origin.prepare(self.session, self.repo)["origins"][0]
        selected = scope.select(session=self.session, cwd=self.repo, task_id="selected-root",
                                origin_ref=item["origin_ref"], relation="independent")
        self.ledger = Path(selected["new_ledger_path"])
        self.data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                     "transcript_path": str(self.transcript)}
        authority.bind_source(self.ledger, self.data)
        self.work = budget.register_review_work(self.ledger, boundary_id="selected-project",
            phase="post_review", agent_type="cp_review_security_access", profile_id="g6-sol-medium",
            scope_paths=["src/app.py"], purpose="Bounded workspace approval fixture.")
        self.request = budget.request_allowance(self.ledger, work_ids=[self.work["work_id"]])
        self.message_count = 0

    def reply(self, *, turn=None, cwd=None):
        if turn is not None:
            self.turn = turn
            self.emit("turn_context", {"turn_id": turn, "cwd": str(cwd or self.repo)})
        self.message_count += 1
        self.emit("response_item", {"type": "message", "role": "user", "id": "approval-" + str(self.message_count),
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": ["user.text"]},
                  "content": [{"type": "input_text", "text": "批准追加额度 " + self.request["request_id"]}]})

    def test_registered_workspace_approval_is_bound_and_idempotent(self):
        source = authority._read_source(authority.source_path(self.ledger))
        self.assertEqual("g6-allowance-native-source/2", source["schema_version"])
        self.reply()
        result = authority.recover(self.ledger)
        self.assertEqual("RECORDED", result["status"])
        self.assertIn(self.request["request_id"], budget.read_budget(self.ledger)["allowance_grants"])
        before = self.ledger.read_bytes()
        authority.recover(self.ledger)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_foreign_workspace_reply_does_not_grant_but_later_project_reply_can(self):
        before = self.ledger.read_bytes()
        self.reply(turn="foreign-turn", cwd=self.initial)
        result = authority.recover(self.ledger)
        self.assertEqual("foreign_workspace", result["applied"][0]["action"])
        self.assertEqual(before, self.ledger.read_bytes())
        self.reply(turn="back-in-project")
        authority.recover(self.ledger)
        self.assertIn(self.request["request_id"], budget.read_budget(self.ledger)["allowance_grants"])

    def test_missing_turn_context_preserves_cursor_and_recovers_without_repeating_reply(self):
        self.turn = "context-not-yet-visible"
        before = self.ledger.read_bytes()
        self.reply()
        result = authority.recover(self.ledger)
        self.assertEqual("WORKSPACE_CONTEXT_PENDING", result["status"])
        self.assertEqual(before, self.ledger.read_bytes())
        self.emit("turn_context", {"turn_id": self.turn, "cwd": str(self.repo)})
        self.observe_parent()
        authority.recover(self.ledger)
        self.assertIn(self.request["request_id"], budget.read_budget(self.ledger)["allowance_grants"])

    def test_source_origin_cannot_be_replaced_by_a_caller_label(self):
        path = authority.source_path(self.ledger)
        source = authority._read_source(path)
        source["workspace_origin_ref"] = "TO1-" + "0" * 32
        atomic_write_json(path, source, seal=True)
        self.reply()
        with self.assertRaisesRegex(ValueError, "WORKSPACE_ROOT_CONFLICT"):
            authority.recover(self.ledger)

    def test_replaced_native_file_cannot_take_over_workspace_approval(self):
        self.reply()
        replacement = self.transcript.with_suffix(".replacement")
        replacement.write_bytes(self.transcript.read_bytes())
        replacement.replace(self.transcript)
        with self.assertRaisesRegex(ValueError, "SOURCE_REPLACED"):
            authority.recover(self.ledger)

    def test_native_context_alone_cannot_bind_an_unregistered_budget(self):
        forged = self.ledger.with_name("unregistered-budget.jsonl")
        current = budget.read_budget(self.ledger)["root"]
        budget.initialize(forged, identity_value=current["identity"], host_session_id=self.session,
                          repo_path=self.repo, task_id="unregistered", authorization_ref=current["authorization_ref"])
        before = forged.read_bytes()
        with self.assertRaisesRegex(ValueError, "WORKSPACE_ROOT_REQUIRED"):
            authority.bind_source(forged, self.data)
        self.assertEqual(before, forged.read_bytes())
        self.assertFalse(authority.source_path(forged).exists())


if __name__ == "__main__":
    unittest.main()
