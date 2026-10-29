"""中文：父子会话共享别名核验；全部文件均为隔离测试夹具。
English: Parent/child account aliases share strict checks using isolated fixtures.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime.g6_task_origin import _native_transcript_path
from cp_runtime.routing_hook_v5 import _transcript_path
from cp_runtime import g6_allowance_authority as authority, g6_budget_v1 as budget
import test_g6_allowance_authority as allowance_fixtures
import test_native_workspace as workspace_fixtures


class NativeTranscriptPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cp-native-path-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "canonical-home"
        self.alias = self.base / "user" / ".codex"
        self.alias.parent.mkdir()
        self.file = self.home / "sessions" / "rollout-child-id.jsonl"
        self.file.parent.mkdir(parents=True)
        self.file.write_text("{}\n", encoding="utf-8")
        self.addCleanup(mock.patch.stopall)
        mock.patch("cp_runtime.common.resolve_codex_home", return_value=self.home).start()
        mock.patch("pathlib.Path.home", return_value=self.alias.parent).start()
        mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home)}).start()

    def link(self, alias, target):
        self.assertTrue(alias.absolute().is_relative_to(self.base))
        self.assertTrue(target.resolve().is_relative_to(self.base))
        if os.name == "nt":
            result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(target)],
                                    capture_output=True, timeout=5)
            if result.returncode:
                self.skipTest("Windows junction creation unavailable")
        else:
            alias.symlink_to(target, target_is_directory=True)

        def remove_link():
            self.assertEqual(alias.resolve(), target.resolve())
            if alias.is_symlink():
                alias.unlink()
            else:
                os.rmdir(alias)
        self.addCleanup(remove_link)

    def child(self, path, event="PreToolUse"):
        field = "agent_transcript_path" if event == "SubagentStop" else "transcript_path"
        return {"session_id": "parent-session", "agent_id": "child-id",
                "hook_event_name": event, field: str(path)}

    def test_canonical_child_path_retains_identity_checks(self):
        self.assertEqual(self.file, _transcript_path(self.child(self.file)))

    def test_verified_account_junction_is_shared_by_parent_and_child(self):
        self.link(self.alias, self.home)
        path = self.alias / "sessions" / self.file.name
        self.assertEqual(self.file, _transcript_path(self.child(path)))
        self.assertEqual(self.file, _native_transcript_path(str(path)))

    def test_subagent_stop_uses_the_same_verified_alias(self):
        self.link(self.alias, self.home)
        path = self.alias / "sessions" / self.file.name
        self.assertEqual(self.file, _transcript_path(self.child(path, "SubagentStop")))

    def test_foreign_account_alias_cannot_gain_equivalence(self):
        foreign = self.base / "foreign"
        (foreign / "sessions").mkdir(parents=True)
        (foreign / "sessions" / self.file.name).write_text("{}\n", encoding="utf-8")
        self.link(self.alias, foreign)
        path = self.alias / "sessions" / self.file.name
        with self.assertRaisesRegex(ValueError, "TASK_NATIVE_HOME_IDENTITY"):
            _transcript_path(self.child(path))

    def test_session_internal_junction_is_still_rejected(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        (foreign / self.file.name).write_text("{}\n", encoding="utf-8")
        link = self.home / "sessions" / "inner"
        self.link(link, foreign)
        with self.assertRaisesRegex(ValueError, "V5_REPARSE_PATH_DENIED"):
            _transcript_path(self.child(link / self.file.name))

    def test_unproven_root_identity_is_not_a_fallback(self):
        with mock.patch.object(Path, "samefile", return_value=False):
            with self.assertRaisesRegex(ValueError, "TASK_NATIVE_HOME_IDENTITY"):
                _transcript_path(self.child(self.file))

    def test_missing_file_identity_proof_is_rejected(self):
        with mock.patch.object(Path, "samefile", side_effect=[True, False]):
            with self.assertRaisesRegex(ValueError, "TASK_NATIVE_HOME_IDENTITY"):
                _transcript_path(self.child(self.file))

    def test_relative_child_path_is_not_made_absolute(self):
        with self.assertRaisesRegex(ValueError, "V5_ABSOLUTE_PATH_REQUIRED"):
            _transcript_path(self.child(Path("sessions") / self.file.name))

    def test_regular_file_outside_native_sessions_is_rejected(self):
        outside = self.base / self.file.name
        outside.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "V5_CHILD_HEADER_PATH"):
            _transcript_path(self.child(outside))

    def test_another_child_filename_is_not_admitted(self):
        other = self.file.with_name("rollout-other-child.jsonl")
        other.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "V5_CHILD_HEADER_PATH"):
            _transcript_path(self.child(other))

    @unittest.skipUnless(os.name == "nt", "Windows alternate streams")
    def test_alternate_stream_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "V5_ALTERNATE_STREAM_DENIED"):
            _transcript_path(self.child(Path(str(self.file) + ":other")))


class ParentAllowancePathTests(unittest.TestCase):
    emit = allowance_fixtures.AllowanceAuthorityTests.emit
    user = allowance_fixtures.AllowanceAuthorityTests.user
    link = NativeTranscriptPathTests.link

    def setUp(self):
        allowance_fixtures.AllowanceAuthorityTests.setUp(self)
        self.base = self.base.resolve()

    def alias_data(self, target=None):
        alias = self.base / "native-user" / ".codex"
        alias.parent.mkdir()
        self.link(alias, target or self.home.resolve())
        return alias, {**self.data, "transcript_path": str(alias / "sessions" / self.transcript.name)}

    def test_v1_native_alias_preserves_cursor_and_existing_approval(self):
        before_source = authority.source_path(self.ledger).read_bytes()
        before_ledger = self.ledger.read_bytes()
        alias, data = self.alias_data()
        with mock.patch("pathlib.Path.home", return_value=alias.parent):
            result = authority.bind_source(self.ledger, data)
            self.assertEqual("g6-allowance-native-source/1", result["schema_version"])
            self.assertEqual(before_source, authority.source_path(self.ledger).read_bytes())
            self.assertEqual(before_ledger, self.ledger.read_bytes())
            self.user("批准追加额度 " + self.request["request_id"])
            authority.recover(self.ledger, data=data)
            self.assertIn(self.request["request_id"], budget.read_budget(self.ledger)["allowance_grants"])
            granted = self.ledger.read_bytes()
            authority.recover(self.ledger, data=data)
            self.assertEqual(granted, self.ledger.read_bytes())

    def test_foreign_allowance_alias_cannot_replace_the_bound_source(self):
        foreign = self.base / "foreign-home"
        (foreign / "sessions").mkdir(parents=True)
        (foreign / "sessions" / self.transcript.name).write_bytes(self.transcript.read_bytes())
        before_source = authority.source_path(self.ledger).read_bytes()
        before_ledger = self.ledger.read_bytes()
        alias, data = self.alias_data(foreign)
        with mock.patch("pathlib.Path.home", return_value=alias.parent):
            with self.assertRaisesRegex(ValueError, "TASK_NATIVE_HOME_IDENTITY"):
                authority.bind_source(self.ledger, data)
        self.assertEqual(before_source, authority.source_path(self.ledger).read_bytes())
        self.assertEqual(before_ledger, self.ledger.read_bytes())


class WorkspaceAllowancePathTests(unittest.TestCase):
    parent = workspace_fixtures.WorkspaceAllowanceTests.parent
    emit = workspace_fixtures.WorkspaceAllowanceTests.emit
    observe_parent = workspace_fixtures.WorkspaceAllowanceTests.observe_parent
    native_user = workspace_fixtures.WorkspaceAllowanceTests.native_user
    change_workspace = workspace_fixtures.WorkspaceAllowanceTests.change_workspace
    reply = workspace_fixtures.WorkspaceAllowanceTests.reply
    link = NativeTranscriptPathTests.link

    def setUp(self):
        workspace_fixtures.WorkspaceAllowanceTests.setUp(self)
        self.base = self.base.resolve()

    def test_v2_native_alias_keeps_the_registered_root_and_approved_cursor(self):
        before_source = authority.source_path(self.ledger).read_bytes()
        before_ledger = self.ledger.read_bytes()
        root = budget.read_budget(self.ledger)["root"]
        home = Path(os.environ["CODEX_HOME"]).resolve()
        alias = self.base / "native-user" / ".codex"
        alias.parent.mkdir()
        self.link(alias, home)
        data = {**self.data, "transcript_path": str(alias / self.transcript.resolve().relative_to(home))}
        with mock.patch("pathlib.Path.home", return_value=alias.parent):
            result = authority.bind_source(self.ledger, data)
            self.assertEqual("g6-allowance-native-source/2", result["schema_version"])
            self.assertEqual(before_source, authority.source_path(self.ledger).read_bytes())
            self.assertEqual(before_ledger, self.ledger.read_bytes())
            self.reply()
            authority.recover(self.ledger, data=data)
            updated = budget.read_budget(self.ledger)
            self.assertEqual(root, updated["root"])
            self.assertIn(self.request["request_id"], updated["allowance_grants"])


if __name__ == "__main__":
    unittest.main()
