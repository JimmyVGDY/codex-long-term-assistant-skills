"""中文：隔离的 Desktop 格式夹具；不迁移真实账户或声称真实宿主验收。
English: Isolated Desktop-format fixtures, not live account migration or host acceptance.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1 as budget, g6_handoff_v1 as legacy
from cp_runtime import g6_task_origin as origin, g6_task_scope as scope, g6_hook_v1 as hook
from cp_runtime.common import utc_now
from cp_runtime.g6_review_controller import _native_root
from cp_runtime.routing_contract import ref


class TaskScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo, self.home = self.base / "workspace", self.base / "home"
        self.repo.mkdir()
        self.session, self.turn, self.count = "parent-fixture", "same-active-turn", 0
        patch = mock.patch.dict(os.environ, CODEX_HOME=str(self.home), CP_DELEGATION_BUDGET_PATH="")
        patch.start()
        self.addCleanup(patch.stop)
        support = mock.patch("cp_runtime.g6_runtime_support.installed_task_scope_support",
                             return_value={"supported": True})
        support.start()
        self.addCleanup(support.stop)
        self.transcript = self.parent(self.session)
        self.emit("session_meta", {"id": self.session, "cwd": str(self.repo), "source": "desktop"})

    def parent(self, session):
        path = self.home / "sessions" / ("rollout-" + session + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def emit(self, kind, payload, *, path=None):
        with (path or self.transcript).open("ab") as stream:
            stream.write((json.dumps({"type": kind, "timestamp": utc_now(), "payload": payload},
                                    ensure_ascii=False) + "\n").encode("utf-8"))

    def user(self, text, *, kinds=None, image=False):
        self.count += 1
        content = [{"type": "input_text", "text": text}]
        if image:
            content.append({"type": "input_image", "image_url": "fixture-image"})
        self.emit("response_item", {"type": "message", "role": "user", "id": "user-" + str(self.count),
                  "internal_chat_message_metadata_passthrough": {
                      "turn_id": self.turn, "content_item_kinds": kinds or ["user.text"]},
                  "content": content})
        origin.observe({"session_id": self.session, "cwd": str(self.repo),
                        "transcript_path": str(self.transcript), "hook_event_name": "UserPromptSubmit"})
        return origin.prepare(self.session, self.repo)["origins"]

    def select(self, task_id, text=None, relation="independent", task_scope=None):
        item = self.user(text or "Implement independent objective " + task_id)[-1]
        return scope.select(session=self.session, cwd=self.repo, task_id=task_id,
                            origin_ref=item["origin_ref"], relation=relation, task_scope=task_scope)

    def preview(self, selected, name="worker"):
        return hook.preview(session_id=self.session, cwd=self.repo, task_scope=selected["task_scope"],
                            agent_type="worker", task_name=name, message="Inspect this synthetic task.")

    def reserve(self, selected, name):
        args = self.preview(selected, name)["exact_tool_parameters"]
        self.assertIsNotNone(args)
        data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                "hook_event_name": "PreToolUse", "tool_use_id": "call-" + name,
                "tool_name": "spawn_agent", "tool_input": args, "transcript_path": str(self.transcript)}
        handled, result = hook.handle(data, "PreToolUse")
        self.assertTrue(handled)
        self.assertEqual(result, {})
        return data

    def post(self, data):
        event = {**data, "hook_event_name": "PostToolUse",
                 "tool_response": {"task_name": "/root/" + data["tool_input"]["task_name"]}}
        self.assertEqual(hook.handle(event, "PostToolUse"), (True, {}))
        return event

    def finish(self, selected, data):
        self.post(data)
        ledger = Path(selected["new_ledger_path"])
        budget.record_terminal(ledger, agent_path="/root/" + data["tool_input"]["task_name"],
                               outcome="UNKNOWN", proof_ref=ref("synthetic-native-stop"))

    def test_independent_b_has_budget_after_a_exhausted_and_resume_preserves_a(self):
        a = self.select("a")
        for i in range(4):
            self.finish(a, self.reserve(a, "a_" + str(i)))
        before = Path(a["new_ledger_path"]).read_bytes()
        self.assertIsNone(self.preview(a, "a_exhausted")["exact_tool_parameters"])
        b = self.select("b")
        self.assertIsNotNone(self.preview(b)["exact_tool_parameters"])
        resumed = self.select("a", "Return to objective A", relation="resume")
        self.assertEqual(resumed["task_scope"], a["task_scope"])
        self.assertEqual(Path(a["new_ledger_path"]).read_bytes(), before)
        self.assertIsNone(self.preview(resumed, "a_retry")["exact_tool_parameters"])

    def test_same_origin_rename_and_continuation_cannot_reset(self):
        a = self.select("a")
        data = self.reserve(a, "one")
        self.finish(a, data)
        before = Path(a["new_ledger_path"]).read_bytes()
        source = list(scope.registry(self.session)["origins"])[-1]
        replay = scope.select(session=self.session, cwd=self.repo, task_id="renamed",
                              origin_ref=source, relation="independent")
        continued = self.select("renamed-label", "继续", relation="continue")
        self.assertEqual(replay["task_scope"], a["task_scope"])
        self.assertEqual(continued["task_scope"], a["task_scope"])
        self.assertEqual(len(scope.registry(self.session)["scopes"]), 1)
        self.assertEqual(Path(a["new_ledger_path"]).read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Windows namespace aliases")
    def test_native_namespace_alias_preserves_task_origin_and_stored_paths(self):
        from cp_runtime.path_identity import _alternate_windows_spelling
        a = self.select("a")
        source_path = origin._directory(self.session) / "source.json"
        before = json.loads(source_path.read_text(encoding="utf-8"))
        before_ledger = Path(a["new_ledger_path"]).read_bytes()
        data = {"session_id": self.session, "cwd": _alternate_windows_spelling(str(self.repo.resolve())),
                "transcript_path": _alternate_windows_spelling(str(self.transcript.resolve())),
                "hook_event_name": "PreToolUse"}
        origin.observe(data)
        origin.observe({**data, "hook_event_name": "UserPromptSubmit"})
        original_origin = origin.prepare(self.session, self.repo)["origins"][-1]["origin_ref"]
        alias_origin = origin.prepare(self.session, Path(data["cwd"]))["origins"][-1]["origin_ref"]
        self.assertEqual(alias_origin, original_origin)
        origin.read_origin(self.session, Path(data["cwd"]), original_origin)
        after = json.loads(source_path.read_text(encoding="utf-8"))
        for key in ("repo_path", "transcript_path", "header_ref", "transcript_file_ref", "transcript_path_ref"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(Path(a["new_ledger_path"]).read_bytes(), before_ledger)

    def test_same_turn_task_switch_does_not_retarget_old_preview_call_or_controller(self):
        a = self.select("a")
        args = self.preview(a, "late_a")["exact_tool_parameters"]
        controller = {"host_session_id": self.session, "repo_path": str(self.repo),
                      "task_id": "a", "ledger_path": a["new_ledger_path"]}
        self.assertEqual(str(_native_root(controller)), a["new_ledger_path"])
        b = self.select("b")
        with self.assertRaisesRegex(ValueError, "TASK_EXPLICIT_SCOPE_REQUIRED"):
            hook.preview(session_id=self.session, cwd=self.repo, agent_type="worker",
                         task_name="old_unnamespaced", message="same task")
        data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                "hook_event_name": "PreToolUse", "tool_use_id": "late-call",
                "tool_name": "spawn_agent", "tool_input": args}
        self.assertEqual(hook.handle(data, "PreToolUse"), (True, {}))
        self.post(data)
        self.assertEqual(str(_native_root(controller)), a["new_ledger_path"])
        self.assertEqual(controller["task_scope"], a["task_scope"])
        self.assertEqual(len(budget.read_budget(Path(b["new_ledger_path"]))["reservations"]), 0)
        resumed = self.select("a", "Repair A", relation="continue")
        self.assertEqual(resumed["task_scope"], a["task_scope"])

    def test_call_id_cannot_cross_scopes_and_late_post_is_idempotent(self):
        a = self.select("a")
        data = self.reserve(a, "old")
        b = self.select("b")
        before_b = Path(b["new_ledger_path"]).read_bytes()
        changed = {**data, "tool_input": self.preview(b)["exact_tool_parameters"]}
        self.assertIn("TASK_CALL_BINDING_CHANGED", hook.handle(changed, "PreToolUse")[1]
                      ["hookSpecificOutput"]["permissionDecisionReason"])
        self.post(data)
        before_a = Path(a["new_ledger_path"]).read_bytes()
        self.post(data)
        self.assertEqual(Path(a["new_ledger_path"]).read_bytes(), before_a)
        self.assertEqual(Path(b["new_ledger_path"]).read_bytes(), before_b)

    def test_child_start_recovers_before_post_then_stop_settles_a_while_b_active(self):
        a = self.select("a")
        data = self.reserve(a, "child")
        b = self.select("b")
        child = self.home / "sessions/rollout-child-fixture.jsonl"
        task = "/root/" + data["tool_input"]["task_name"]
        self.emit("session_meta", {"id": "child-fixture", "cwd": str(self.repo),
                  "source": {"subagent": {"thread_spawn": {
                      "parent_thread_id": self.session, "depth": 1, "agent_role": "worker", "agent_path": task}}}}, path=child)
        event = {"session_id": self.session, "cwd": str(self.repo), "turn_id": "child-turn",
                 "agent_id": "child-fixture", "agent_type": "worker", "transcript_path": str(child),
                 "hook_event_name": "SubagentStart"}
        self.assertEqual(hook.handle(event, "SubagentStart"), (True, {}))
        context = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "hooks/cp_context.py"),
                                  "PreToolUse"], input=json.dumps({**event, "hook_event_name": "PreToolUse",
                                  "tool_name": "exec_command", "tool_input": {"command": "read fixture"},
                                  "tool_use_id": "child-local-read"}), text=True, capture_output=True, timeout=15)
        self.assertEqual(context.returncode, 0, context.stderr)
        self.assertEqual(json.loads(context.stdout), {})
        self.emit("turn_context", {"turn_id": "child-turn"}, path=child)
        self.emit("response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
                  "content": [{"type": "output_text", "text": "Fixture complete."}]}, path=child)
        self.emit("event_msg", {"type": "task_complete", "turn_id": "child-turn"}, path=child)
        self.assertEqual(hook.handle({**event, "hook_event_name": "SubagentStop",
                                    "agent_transcript_path": str(child)}, "SubagentStop"), (True, {}))
        self.post(data)
        state_a = budget.read_budget(Path(a["new_ledger_path"]))
        self.assertEqual(len(state_a["receipts"]), 1)
        self.assertEqual(len(state_a["terminals"]), 1)
        self.assertFalse(budget.read_budget(Path(b["new_ledger_path"]))["receipts"])
        continued = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                     "hook_event_name": "PreToolUse", "tool_use_id": "continue-old",
                     "tool_name": "followup_task", "tool_input": {"target": "child-fixture", "message": "Retry A"}}
        self.assertEqual(scope.route(continued), ("new", Path(a["new_ledger_path"])))
        self.assertEqual(hook.handle(continued, "PreToolUse"), (True, {}))
        self.assertEqual(len(budget.read_budget(Path(a["new_ledger_path"]))["reservations"]), 2)
        self.assertFalse(budget.read_budget(Path(b["new_ledger_path"]))["reservations"])

    def test_completion_requires_settlement_and_does_not_erase_budget(self):
        a = self.select("a")
        data = self.reserve(a, "one")
        with self.assertRaisesRegex(ValueError, "TASK_NATIVE_OUTCOME_PENDING"):
            scope.complete(self.session, self.repo, a["task_scope"])
        self.finish(a, data)
        before = Path(a["new_ledger_path"]).read_bytes()
        self.assertEqual(scope.complete(self.session, self.repo, a["task_scope"])["status"], "COMPLETE")
        resumed = self.select("a", "Continue A", relation="resume")
        self.assertEqual(resumed["task_scope"], a["task_scope"])
        self.assertEqual(Path(a["new_ledger_path"]).read_bytes(), before)

    def test_migration_preserves_old_bytes_and_old_reader_fails_closed(self):
        hook._ensure_new_session({"session_id": self.session, "cwd": str(self.repo), "task_id": "original"})
        old_binding = legacy.read(self.session)
        old = Path(old_binding["new_ledger_path"])
        pointer_before, ledger_before = legacy.pointer_for(self.session).read_bytes(), old.read_bytes()
        a = self.select("a", "Continue existing work", relation="continue")
        self.assertEqual(a["new_ledger_path"], str(old))
        self.select("b")
        self.assertEqual(old.read_bytes(), ledger_before)
        archive = scope._legacy_directory(self.session) / legacy.pointer_for(self.session).name
        self.assertEqual(archive.read_bytes(), pointer_before)
        with self.assertRaises(ValueError):
            legacy.read(self.session)
        self.assertEqual(scope.read(self.session, ledger_path=old)["task_scope"], a["task_scope"])

    def test_pointer_publish_crash_retries_same_root_and_parallel_selects_do_not_duplicate(self):
        source = self.user("Implement A")[-1]["origin_ref"]
        args = dict(session=self.session, cwd=self.repo, task_id="a", origin_ref=source, relation="independent")
        original = scope.atomic_write_json
        def crash(path, *a, **kw):
            if path == legacy.pointer_for(self.session):
                raise OSError("simulated interruption")
            return original(path, *a, **kw)
        with mock.patch.object(scope, "atomic_write_json", side_effect=crash):
            with self.assertRaises(OSError):
                scope.select(**args)
        roots = list((scope._home() / "roots").glob("*.jsonl"))
        self.assertEqual(len(roots), 1)
        before = roots[0].read_bytes()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda _: scope.select(**args), range(2)))
        self.assertEqual(outputs[0]["task_scope"], outputs[1]["task_scope"])
        self.assertEqual(roots[0].read_bytes(), before)
        self.assertEqual(len(list((scope._home() / "roots").glob("*.jsonl"))), 1)

    def test_cross_chat_same_registered_task_requires_handoff(self):
        self.select("a")
        self.session = "other-parent"
        self.transcript = self.parent(self.session)
        self.emit("session_meta", {"id": self.session, "cwd": str(self.repo), "source": "desktop"})
        with self.assertRaisesRegex(ValueError, "TASK_EXISTING_ROOT_HANDOFF_REQUIRED"):
            self.select("a")

    def test_foreign_task_conflict_does_not_poison_same_origin_retry(self):
        original = self.select("a")
        before = Path(original["new_ledger_path"]).read_bytes()
        self.session = "other-parent"
        self.transcript = self.parent(self.session)
        self.emit("session_meta", {"id": self.session, "cwd": str(self.repo), "source": "desktop"})
        source = self.user("Implement another independent objective")[-1]["origin_ref"]
        args = dict(session=self.session, cwd=self.repo, task_id="a",
                    origin_ref=source, relation="independent")
        with self.assertRaisesRegex(ValueError, "TASK_EXISTING_ROOT_HANDOFF_REQUIRED"):
            scope.select(**args)
        selected = scope.select(**{**args, "task_id": "b"})
        self.assertEqual(selected["task_id"], "b")
        self.assertNotEqual(selected["task_scope"], original["task_scope"])
        self.assertEqual(Path(original["new_ledger_path"]).read_bytes(), before)
        self.assertEqual(len(list((scope._home() / "roots").glob("*.jsonl"))), 2)

    def test_completed_scope_rejects_prepared_permit_until_explicit_resume(self):
        a = self.select("a")
        args = self.preview(a, "delayed")["exact_tool_parameters"]
        scope.complete(self.session, self.repo, a["task_scope"])
        self.select("b")
        data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                "hook_event_name": "PreToolUse", "tool_use_id": "late-dispatch",
                "tool_name": "spawn_agent", "tool_input": args}
        result = hook.handle(data, "PreToolUse")[1]
        self.assertIn("TASK_SCOPE_COMPLETE_RESUME_REQUIRED",
                      result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertFalse(budget.read_budget(Path(a["new_ledger_path"]))["reservations"])
        self.select("a", "Resume objective A", relation="resume")
        self.assertEqual(hook.handle(data, "PreToolUse"), (True, {}))
        self.finish(a, data)
        scope.complete(self.session, self.repo, a["task_scope"])
        self.post(data)

    def test_completion_cannot_interleave_active_check_and_reservation(self):
        a = self.select("a")
        args = self.preview(a, "racing")["exact_tool_parameters"]
        data = {"session_id": self.session, "cwd": str(self.repo), "turn_id": self.turn,
                "hook_event_name": "PreToolUse", "tool_use_id": "race-dispatch",
                "tool_name": "spawn_agent", "tool_input": args}
        reached, release, completing = Event(), Event(), Event()
        reserve = budget.approve_and_reserve
        def delayed(*args, **kwargs):
            reached.set()
            if not release.wait(1):
                raise AssertionError("reservation release timed out")
            return reserve(*args, **kwargs)
        def complete():
            completing.set()
            return scope.complete(self.session, self.repo, a["task_scope"])
        with mock.patch.object(budget, "approve_and_reserve", side_effect=delayed):
            with ThreadPoolExecutor(max_workers=2) as pool:
                admission = pool.submit(hook.handle, data, "PreToolUse")
                self.assertTrue(reached.wait(1))
                closure = pool.submit(complete)
                self.assertTrue(completing.wait(1))
                self.assertFalse(closure.done())
                release.set()
                self.assertEqual(admission.result(), (True, {}))
                with self.assertRaisesRegex(ValueError, "TASK_NATIVE_OUTCOME_PENDING"):
                    closure.result()

    def test_crash_then_rename_reuses_frozen_origin_before_root_initialization(self):
        source = self.user("Implement objective A")[-1]["origin_ref"]
        args = dict(session=self.session, cwd=self.repo, task_id="a",
                    origin_ref=source, relation="independent")
        original = scope.atomic_write_json
        def crash(path, *a, **kw):
            if path == legacy.pointer_for(self.session):
                raise OSError("fixture interruption")
            return original(path, *a, **kw)
        with mock.patch.object(scope, "atomic_write_json", side_effect=crash):
            with self.assertRaises(OSError):
                scope.select(**args)
        first = next((scope._home() / "roots").glob("*.jsonl"))
        before = first.read_bytes()
        recovered = scope.select(**{**args, "task_id": "renamed-a"})
        self.assertEqual(recovered["task_id"], "a")
        self.assertEqual(Path(recovered["new_ledger_path"]), first)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(len(list((scope._home() / "roots").glob("*.jsonl"))), 1)

    def test_late_post_with_new_turn_metadata_keeps_frozen_original_task(self):
        a = self.select("a")
        data = self.reserve(a, "old_a")
        self.turn = "next-parent-turn"
        b = self.select("b")
        before_b = Path(b["new_ledger_path"]).read_bytes()
        self.post({**data, "turn_id": self.turn})
        self.assertEqual(len(budget.read_budget(Path(a["new_ledger_path"]))["receipts"]), 1)
        self.assertEqual(Path(b["new_ledger_path"]).read_bytes(), before_b)
        call = scope._sealed(scope._call_path(self.session, data["tool_use_id"]))
        self.assertEqual(call["turn_ref"], ref(data["turn_id"]))

    def test_origin_accepts_image_text_but_not_automatic_goal_or_approval(self):
        rows = self.user("Fix the attached example", kinds=["user.text", "user.image"], image=True)
        selected = rows[-1]
        self.assertEqual(origin.read_origin(self.session, self.repo, selected["origin_ref"])["kind"], "goal_candidate")
        self.user("automatically continue", kinds=["additional_content.goal"])
        self.assertEqual(origin.prepare(self.session, self.repo)["origins"][-1], selected)
        rows = self.user("<send_user_message_question_reply>[]</send_user_message_question_reply>")
        with self.assertRaisesRegex(ValueError, "TASK_INDEPENDENT_GOAL_SOURCE_REQUIRED"):
            scope.select(session=self.session, cwd=self.repo, task_id="forbidden",
                         origin_ref=rows[-1]["origin_ref"], relation="independent")
        stored = "\n".join(p.read_text(encoding="utf-8") for p in origin._directory(self.session).glob("*.json"))
        self.assertNotIn("Fix the attached example", stored)

    def test_mutated_origin_and_foreign_repo_are_rejected(self):
        item = self.user("Implement A")[-1]
        other = self.base / "foreign"
        other.mkdir()
        with self.assertRaises(ValueError):
            origin.read_origin(self.session, other, item["origin_ref"])
        self.transcript.write_bytes(self.transcript.read_bytes().replace(b"Implement A", b"Implement B"))
        with self.assertRaisesRegex(ValueError, "TASK_ORIGIN_CHANGED"):
            origin.read_origin(self.session, self.repo, item["origin_ref"])

    def test_uninstalled_reader_cannot_publish_scope(self):
        item = self.user("Implement A")[-1]
        with mock.patch("cp_runtime.g6_runtime_support.installed_task_scope_support", return_value={"supported": False}):
            with self.assertRaisesRegex(ValueError, "TASK_MATCHING_INSTALLED_READER_REQUIRED"):
                scope.select(session=self.session, cwd=self.repo, task_id="a",
                             origin_ref=item["origin_ref"], relation="independent")
        self.assertFalse(legacy.pointer_for(self.session).exists())

    def test_damaged_budget_registry_does_not_block_parent_read_or_write_tool(self):
        self.select("a")
        legacy.pointer_for(self.session).write_text("{invalid", encoding="utf-8")
        for tool in ("exec_command", "apply_patch"):
            event = {"hook_event_name": "PreToolUse", "session_id": self.session,
                     "cwd": str(self.repo), "tool_name": tool, "tool_use_id": "unrelated",
                     "tool_input": {"command": "fixture"}}
            self.assertEqual(hook.handle(event, "PreToolUse"), (False, None))


if __name__ == "__main__":
    unittest.main()
