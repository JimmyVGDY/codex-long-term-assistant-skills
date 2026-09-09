"""中文：可选策略、原子任务状态和有界补救；不替代宿主及完成证据验收。

English: Optional policy, atomic task state, and bounded repair; not host/completion acceptance.
"""
from __future__ import annotations

import json
import multiprocessing
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime.capability_gate import GatePolicy, GateTask
from cp_runtime.capability_store import CapabilityError, CapabilityStore
from cp_runtime.common import canonical_json, seal_record


def repair_process(profile, repo, root, ready, go, result):
    policy = GatePolicy(CapabilityStore(Path(profile), Path(repo)), Path(root))
    task = GateTask(policy, "session", "turn")
    ready.put(True)
    go.wait(10)
    try:
        result.put(task.request_repair(False, ["NEEDS_PREPARE"])["action"])
    except Exception as exc:
        result.put(type(exc).__name__)


class CapabilityGateTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def gate(self):
        return GatePolicy(self.store, self.base / "gate-config")

    def task(self):
        policy = self.gate()
        policy.set_enabled(True, None)
        task = GateTask(policy, "session", "turn")
        task.create("a" * 64)
        return task

    def test_missing_policy_has_no_writes_and_enable_preserves_profile_and_index(self):
        policy = self.gate()
        before = {p.name: p.read_bytes() for p in self.profile.parent.iterdir() if p.is_file()}
        self.assertIsNone(policy.read())
        self.assertFalse(policy.root.exists())
        enabled = policy.set_enabled(True, None)
        self.assertEqual(0, enabled["revision"])
        self.assertFalse(self.store.current.exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.parent.iterdir() if p.is_file()})
        with patch("cp_runtime.capability_gate.atomic_write_bytes", side_effect=AssertionError("Unexpected rewrite")):
            self.assertEqual(enabled, policy.set_enabled(True, 0))

    def test_policy_conflict_disable_and_reenable_cannot_reuse_previous_task(self):
        task = self.task()
        with self.assertRaisesRegex(CapabilityError, "REVISION_CONFLICT"):
            task.policy.set_enabled(False, 4)
        task.policy.set_enabled(False, 0)
        with self.assertRaisesRegex(CapabilityError, "POLICY_CHANGED"):
            task.read()
        task.policy.set_enabled(True, 1)
        replacement = GateTask(task.policy, "session", "turn")
        self.assertNotEqual(task.path, replacement.path)
        self.assertTrue(task.path.exists())
        with self.assertRaisesRegex(CapabilityError, "TASK_MISSING"):
            replacement.read()

    def test_prepare_is_idempotent_and_pass_requires_preparation(self):
        task = self.task()
        with self.assertRaisesRegex(CapabilityError, "PREPARE_REQUIRED"):
            task.finish("PASS", "c" * 64, 0)
        prepared = task.record_prepared("b" * 64, 0)
        original = task.path.read_bytes()
        with patch("cp_runtime.capability_gate.atomic_write_bytes", side_effect=AssertionError("Unexpected rewrite")):
            self.assertEqual(prepared, task.record_prepared("b" * 64, prepared["revision"]))
        self.assertEqual(original, task.path.read_bytes())
        passed = task.finish("PASS", "c" * 64, prepared["revision"])
        self.assertEqual("PASS", passed["phase"])
        stale = task.invalidate_completion()
        self.assertEqual("BLOCKED", stale["phase"])
        with self.assertRaisesRegex(CapabilityError, "TERMINAL"):
            task.finish("PASS", "d" * 64, stale["revision"])

    def test_stop_replay_never_requests_a_second_continuation(self):
        task = self.task()
        first = task.request_repair(False, ["NEEDS_PREPARE"])
        second = task.request_repair(False, ["NEEDS_PREPARE"])
        self.assertEqual("CONTINUE", first["action"])
        self.assertEqual("HALT", second["action"])
        self.assertEqual(1, second["state"]["repair_count"])
        self.assertEqual(["STOP_REPLAY"], second["state"]["reason_codes"])

    def test_progress_does_not_reset_two_repair_limit(self):
        task = self.task()
        first = task.request_repair(False, ["NEEDS_PREPARE"])
        prepared = task.record_prepared("b" * 64, first["state"]["revision"])
        second = task.request_repair(True, ["NEEDS_FINISH"])
        task.record_prepared("c" * 64, second["state"]["revision"])
        third = task.request_repair(True, ["NEEDS_FINISH"])
        self.assertEqual("CONTINUE", second["action"])
        self.assertEqual("HALT", third["action"])
        self.assertEqual(2, third["state"]["repair_count"])
        self.assertEqual(["REPAIR_LIMIT"], third["state"]["reason_codes"])
        self.assertEqual(1, prepared["progress_revision"])

    def test_cancel_wins_over_later_finish_and_stop(self):
        task = self.task()
        first = task.request_repair(False, ["NEEDS_PREPARE"])
        cancelled = task.cancel()
        self.assertGreater(cancelled["revision"], first["state"]["revision"])
        self.assertEqual(cancelled, task.cancel())
        self.assertEqual("HALT", task.request_repair(True, ["NEEDS_PREPARE"])["action"])
        with self.assertRaisesRegex(CapabilityError, "TERMINAL"):
            task.record_prepared("b" * 64, cancelled["revision"])

    def test_partial_is_terminal_and_not_auto_repaired(self):
        task = self.task()
        partial = task.finish("PARTIAL", "c" * 64, 0, ["PARTIAL_COVERAGE"])
        self.assertEqual("HALT", task.request_repair(False, ["NEEDS_PREPARE"])["action"])
        self.assertEqual(partial, task.read())
        with self.assertRaisesRegex(CapabilityError, "TERMINAL"):
            task.finish("PASS", "d" * 64, partial["revision"])

    def test_failed_persistence_does_not_emit_continue_or_advance_count(self):
        task = self.task()
        before = task.path.read_bytes()
        with patch("cp_runtime.capability_gate.atomic_write_bytes", side_effect=OSError("injected")):
            with self.assertRaisesRegex(CapabilityError, "COMMIT_UNCERTAIN"):
                task.request_repair(False, ["NEEDS_PREPARE"])
        self.assertEqual(before, task.path.read_bytes())
        self.assertEqual(0, task.read()["repair_count"])

    def test_corrupt_duplicate_and_wrong_task_records_fail_closed(self):
        task = self.task()
        original = task.path.read_bytes()
        cases = [b'{"revision":0,"revision":1}', b'not-json']
        other = json.loads(original)
        other["identity"]["turn_id"] = "other-turn"
        cases.append((canonical_json(seal_record(other)) + "\n").encode())
        for raw in cases:
            with self.subTest(raw=raw[:20]):
                task.path.write_bytes(raw)
                with self.assertRaises(CapabilityError):
                    task.request_repair(False, ["NEEDS_PREPARE"])
                self.assertEqual(raw, task.path.read_bytes())
        task.path.write_bytes(original)
        with self.assertRaisesRegex(CapabilityError, "HOST_IDENTITY_MISSING"):
            GateTask(task.policy, "", "turn")

    def test_concurrent_stop_only_one_process_can_request_continuation(self):
        task = self.task()
        ctx = multiprocessing.get_context("spawn")
        ready, result, go = ctx.Queue(), ctx.Queue(), ctx.Event()
        children = [ctx.Process(target=repair_process, args=(str(self.profile), str(self.repo),
                    str(task.policy.root), ready, go, result)) for _ in range(2)]
        try:
            for child in children:
                child.start()
            for _ in children:
                self.assertTrue(ready.get(timeout=20))
            go.set()
            actions = [result.get(timeout=25) for _ in children]
            for child in children:
                child.join(10)
                self.assertEqual(0, child.exitcode)
            self.assertCountEqual(["CONTINUE", "HALT"], actions)
            self.assertEqual(1, task.read()["repair_count"])
        finally:
            for child in children:
                if child.is_alive():
                    child.terminate()
                    child.join(5)
            ready.close()
            result.close()

    def test_policy_unknown_schema_duplicate_and_identity_mismatch_are_not_disabled(self):
        task = self.task()
        policy = task.policy
        original = policy.path.read_bytes()
        wrong_version = json.loads(original)
        wrong_version["schema_version"] = True
        wrong_identity = json.loads(original)
        wrong_identity["identity"]["project_id"] = "ANOTHER"
        cases = [(canonical_json(seal_record(value)) + "\n").encode()
                 for value in (wrong_version, wrong_identity)]
        cases.append(b'{"enabled":false,"enabled":true}')
        for raw in cases:
            with self.subTest(prefix=raw[:30]):
                policy.path.write_bytes(raw)
                with self.assertRaises(CapabilityError):
                    policy.read()
                self.assertEqual(raw, policy.path.read_bytes())

    def test_new_turn_cannot_read_old_task_or_replace_baseline(self):
        task = self.task()
        other = GateTask(task.policy, "session", "next-turn")
        self.assertNotEqual(task.path, other.path)
        with self.assertRaisesRegex(CapabilityError, "TASK_MISSING"):
            other.read()
        before = task.path.read_bytes()
        with self.assertRaisesRegex(CapabilityError, "BASELINE_CONFLICT"):
            task.create("b" * 64)
        self.assertEqual(before, task.path.read_bytes())
        self.assertEqual(task.read(), task.create("a" * 64))

    def test_stale_revision_and_oversize_task_preserve_existing_evidence(self):
        task = self.task()
        task.record_prepared("b" * 64, 0)
        before = task.path.read_bytes()
        with self.assertRaisesRegex(CapabilityError, "REVISION_CONFLICT"):
            task.finish("PASS", "c" * 64, 0)
        self.assertEqual(before, task.path.read_bytes())
        oversized = b"x" * (256 * 1024 + 1)
        task.path.write_bytes(oversized)
        with self.assertRaisesRegex(CapabilityError, "RECORD_INVALID"):
            task.read()
        self.assertEqual(oversized, task.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
