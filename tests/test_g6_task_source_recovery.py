"""中文：缺少 Hook 时从真实格式记录恢复，保留身份和预算边界。
English: Recover missing Hook provenance from native-format records, preserving identity and budgets.
"""
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from cp_runtime import g6_task_origin as origin, g6_task_scope as scope
import test_g6_task_scope as fixtures


class NativeSourceRecoveryTests(unittest.TestCase):
    setUp = fixtures.TaskScopeTests.setUp
    parent = fixtures.TaskScopeTests.parent
    emit = fixtures.TaskScopeTests.emit

    def observe_parent(self):
        return origin.observe_native_locator({"session_id": self.session, "cwd": str(self.repo),
            "transcript_path": str(self.transcript), "turn_id": self.turn,
            "tool_use_id": "native-fixture-call", "hook_event_name": "PreToolUse"})

    def native_user(self, *, observed=True):
        self.emit("response_item", {
            "type": "message", "role": "user", "id": "native-user-1",
            "internal_chat_message_metadata_passthrough": {
                "turn_id": self.turn, "content_item_kinds": ["user.text"]},
            "content": [{"type": "input_text", "text": "Fix this issue through public release"}]})
        if observed:
            self.observe_parent()

    def test_missing_source_has_readonly_actionable_diagnostics(self):
        result = origin.diagnose(self.session, self.repo)
        self.assertEqual(result["reason_code"], "TASK_NATIVE_SOURCE_UNAVAILABLE")
        self.assertEqual(result["hooks_registration"], "MISSING")
        self.assertEqual(result["next_action"], "repair_hook_registration")
        self.assertFalse(result["repeat_user_input_required"])
        self.assertEqual(result["execution_authorization"], "NONE")
        self.assertFalse(origin._directory(self.session).exists())

    def test_native_readback_recovers_without_repeated_user_input_or_budget(self):
        self.native_user()
        native_before = self.transcript.read_bytes()
        result = origin.recover_source(self.session, self.repo, self.transcript)
        self.assertEqual(result["status"], "RECOVERED")
        self.assertEqual(result["provenance"], "native_hook_locator_readback")
        rows = origin.prepare(self.session, self.repo)["origins"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "goal_candidate")
        self.assertEqual(self.transcript.read_bytes(), native_before)
        self.assertIsNone(scope.registry(self.session))
        self.assertEqual(result["execution_authorization"], "NONE")
        saved = "\n".join(p.read_text(encoding="utf-8") for p in origin._directory(self.session).glob("*.json"))
        self.assertNotIn("Fix this issue", saved)

    def test_repeat_recovery_is_idempotent_and_preserves_source(self):
        self.native_user()
        origin.recover_source(self.session, self.repo, self.transcript)
        path = origin._directory(self.session) / "source.json"
        before = path.read_bytes()
        self.emit("event_msg", {"type": "task_started", "turn_id": "later"})
        result = origin.recover_source(self.session, self.repo, self.transcript)
        self.assertEqual(result["status"], "ALREADY_BOUND")
        self.assertEqual(path.read_bytes(), before)

    def test_recovery_rejects_foreign_session_repo_child_and_outside_source(self):
        self.native_user()
        for session, repo, path in (
            ("foreign", self.repo, self.transcript),
            (self.session, self.base, self.transcript),
            (self.session, self.repo, self.base / self.transcript.name),
        ):
            if not path.exists():
                path.write_bytes(self.transcript.read_bytes())
            with self.subTest(session=session, repo=repo, path=path), self.assertRaises(ValueError):
                origin.recover_source(session, repo, path)
        self.transcript.write_text(json.dumps({"type": "session_meta", "payload": {
            "id": self.session, "cwd": str(self.repo), "source": {"subagent": {}}}}) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "NATIVE_SOURCE_IDENTITY"):
            origin.recover_source(self.session, self.repo, self.transcript)
        self.assertFalse((origin._directory(self.session) / "source.json").exists())

    def test_corrupt_or_conflicting_existing_source_cannot_be_replaced(self):
        self.native_user()
        origin.recover_source(self.session, self.repo, self.transcript)
        path = origin._directory(self.session) / "source.json"
        path.write_text('{"broken":true}', encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises((ValueError, RuntimeError)):
            origin.recover_source(self.session, self.repo, self.transcript)
        self.assertEqual(path.read_bytes(), before)
        result = origin.diagnose(self.session, self.repo)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["next_action"], "inspect_existing_source_integrity")

    def test_recovery_requires_matching_installed_reader(self):
        self.native_user()
        with mock.patch("cp_runtime.g6_runtime_support.installed_task_scope_support", return_value={"supported": False}):
            with self.assertRaisesRegex(ValueError, "TASK_MATCHING_INSTALLED_READER_REQUIRED"):
                origin.recover_source(self.session, self.repo, self.transcript)
        self.assertFalse((origin._directory(self.session) / "source.json").exists())

    def test_concurrent_recovery_creates_one_source_and_no_root(self):
        self.native_user()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: origin.recover_source(self.session, self.repo, self.transcript), range(2)))
        self.assertEqual(sorted(item["status"] for item in results), ["ALREADY_BOUND", "RECOVERED"])
        self.assertIsNone(scope.registry(self.session))

    def test_recovery_preserves_existing_root_and_rejects_file_replacement(self):
        self.native_user()
        origin.recover_source(self.session, self.repo, self.transcript)
        item = origin.prepare(self.session, self.repo)["origins"][0]
        selected = scope.select(session=self.session, cwd=self.repo, task_id="existing",
                                origin_ref=item["origin_ref"], relation="independent")
        ledger = Path(selected["new_ledger_path"])
        before = ledger.read_bytes()
        origin.recover_source(self.session, self.repo, self.transcript)
        self.assertEqual(ledger.read_bytes(), before)
        replacement = self.transcript.with_suffix(".replacement")
        replacement.write_bytes(self.transcript.read_bytes())
        os.replace(replacement, self.transcript)
        with self.assertRaisesRegex(ValueError, "TASK_SOURCE_REPLACED"):
            origin.recover_source(self.session, self.repo, self.transcript)
        self.assertEqual(ledger.read_bytes(), before)

    def test_unsupported_reader_diagnostic_does_not_request_another_reply(self):
        result = origin.diagnose(self.session, self.repo, error=ValueError("TASK_MATCHING_INSTALLED_READER_REQUIRED"))
        self.assertEqual(result["next_action"], "repair_matching_installation")
        self.assertFalse(result["repeat_user_input_required"])

    def test_long_chat_recovers_prior_user_with_bounded_backward_cursor(self):
        self.native_user()
        for _ in range(20):
            self.emit("event_msg", {"type": "tool_output", "data": "x" * 350})
        origin.recover_source(self.session, self.repo, self.transcript)
        before = None
        found = []
        with mock.patch.object(origin, "MAX_WINDOW", 1024):
            for _ in range(20):
                result = origin.prepare(self.session, self.repo, before_byte=before)
                self.assertLessEqual(result["bytes_read"], 1024)
                found.extend(result["origins"])
                following = result["next_before_byte"]
                if following is None:
                    break
                if before is not None:
                    self.assertLess(following, before)
                before = following
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["kind"], "goal_candidate")
        self.assertIsNone(scope.registry(self.session))

    def test_recovered_control_reply_still_cannot_create_an_independent_budget(self):
        self.emit("response_item", {"type": "message", "role": "user", "id": "reply",
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": ["user.text"]},
                  "content": [{"type": "input_text", "text": "<send_user_message_question_reply>[]</send_user_message_question_reply>"}]})
        self.observe_parent()
        origin.recover_source(self.session, self.repo, self.transcript)
        item = origin.prepare(self.session, self.repo)["origins"][0]
        with self.assertRaisesRegex(ValueError, "TASK_INDEPENDENT_GOAL_SOURCE_REQUIRED"):
            scope.select(session=self.session, cwd=self.repo, task_id="forbidden",
                         origin_ref=item["origin_ref"], relation="independent")

    def test_caller_created_transcript_without_host_locator_cannot_create_source(self):
        self.native_user(observed=False)
        with self.assertRaisesRegex(ValueError, "TASK_NATIVE_LOCATOR_UNAVAILABLE"):
            origin.recover_source(self.session, self.repo, self.transcript)
        self.assertFalse((origin._directory(self.session) / "source.json").exists())
        self.assertIsNone(scope.registry(self.session))

    def test_parent_hook_captures_locator_then_origins_recovers_without_user_repeat(self):
        self.native_user(observed=False)
        root = Path(__file__).resolve().parents[1]
        data = {"session_id": self.session, "cwd": str(self.repo), "transcript_path": str(self.transcript),
                "turn_id": self.turn, "tool_use_id": "actual-shaped-tool",
                "tool_name": "exec_command", "tool_input": {"command": "fixture"}}
        result = subprocess.run([sys.executable, "-B", str(root / "hooks/cp_context.py"), "PreToolUse"],
                                input=json.dumps(data), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertFalse((origin._directory(self.session) / "source.json").exists())
        self.assertEqual(len(origin.prepare(self.session, self.repo)["origins"]), 1)
        self.assertIsNone(scope.registry(self.session))

    def test_observation_diagnostic_is_nonblocking_and_contains_no_body_or_paths(self):
        self.native_user(observed=False)
        root = Path(__file__).resolve().parents[1]
        data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                "tool_use_id": "missing-path", "tool_input": {"command": "PRIVATE_COMMAND_BODY"}}
        result = subprocess.run([sys.executable, "-B", str(root / "hooks/cp_context.py"), "PreToolUse"],
                                input=json.dumps(data), capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(result.stdout), {})
        diagnostic = origin.diagnose(self.session, self.repo)["last_native_observation"]
        self.assertEqual(diagnostic["reason_code"], "TASK_NATIVE_LOCATOR_FIELDS_MISSING")
        self.assertFalse(diagnostic["fields_present"]["transcript_path"])
        raw = (origin._directory(self.session) / "observation-diagnostic.json").read_text()
        self.assertNotIn("PRIVATE_COMMAND_BODY", raw)
        self.assertNotIn(str(self.repo), raw)
        self.assertNotIn(str(self.transcript), raw)
        self.assertFalse((origin._directory(self.session) / "source.json").exists())

    def test_header_to_anchor_replacement_never_persists_mixed_binding(self):
        self.native_user(observed=False)
        original = origin._native_header
        calls = 0
        def replace_after_header(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                replacement = self.transcript.with_suffix(".replacement")
                replacement.write_bytes(self.transcript.read_bytes() + b"\n")
                os.replace(replacement, self.transcript)
            return value
        with mock.patch.object(origin, "_native_header", side_effect=replace_after_header):
            with self.assertRaisesRegex(ValueError, "TASK_SOURCE_CHANGED"):
                self.observe_parent()
        self.assertFalse((origin._directory(self.session) / "native-locator.json").exists())

    def test_parent_locator_refresh_finds_new_goal_without_rewriting_old_source(self):
        self.native_user()
        origin.recover_source(self.session, self.repo)
        source = origin._directory(self.session) / "source.json"
        before = source.read_bytes()
        for _ in range(20):
            self.emit("event_msg", {"type": "tool_output", "data": "x" * 350})
        self.emit("response_item", {"type": "message", "role": "user", "id": "later-user",
            "internal_chat_message_metadata_passthrough": {"turn_id": "later", "content_item_kinds": ["user.text"]},
            "content": [{"type": "input_text", "text": "A later independent objective"}]})
        self.observe_parent()
        with mock.patch.object(origin, "MAX_WINDOW", 1024):
            result = origin.prepare(self.session, self.repo)
        self.assertEqual(len(result["origins"]), 1)
        self.assertEqual(result["origins"][0]["kind"], "goal_candidate")
        self.assertEqual(source.read_bytes(), before)

    def test_native_account_alias_is_verified_but_nested_links_still_fail(self):
        self.native_user(observed=False)
        alias = self.base / "account-alias"
        nested = self.home / "sessions" / "nested"
        def link(path, target):
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.addCleanup(path.rmdir)
            else:
                path.symlink_to(target, target_is_directory=True)
                self.addCleanup(path.unlink)
        link(alias, self.home)
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(alias)}):
            data = {"session_id": self.session, "cwd": str(self.repo),
                    "transcript_path": str(alias / "sessions" / self.transcript.name),
                    "turn_id": self.turn, "tool_use_id": "alias-call", "hook_event_name": "PreToolUse"}
            value = origin.observe_native_locator(data)
            self.assertEqual(Path(value["transcript_path"]), self.transcript.resolve())
            self.assertEqual(origin.recover_source(self.session, self.repo)["status"], "RECOVERED")
            link(nested, self.home / "sessions")
            data["transcript_path"] = str(alias / "sessions" / "nested" / self.transcript.name)
            with self.assertRaisesRegex(RuntimeError, "LINK_REJECTED"):
                origin.observe_native_locator(data)

    def test_cli_missing_source_is_json_without_traceback(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-B", str(root / "scripts/cp-runtime.py"),
                                 "task-scope-origins", "--session-id", self.session,
                                 "--repo-path", str(self.repo)], env=os.environ.copy(),
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason_code"], "TASK_NATIVE_SOURCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
