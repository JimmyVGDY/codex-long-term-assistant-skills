"""中文：以真实 Git 文件变化验证门禁证据，不把状态字段当作执行证明。

English: Verify gate evidence against real Git/file changes rather than state labels.
"""
from __future__ import annotations

import copy
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime.capability_gate_evidence import (
    GitView, _bounded_process, capture_worktree, changed_paths, prepare_files, verify_files,
)
from cp_runtime.capability_store import CapabilityError


class CapabilityGateEvidenceTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def write(self, path, text):
        (self.repo / path).write_text(text, encoding="utf-8")

    def test_clean_start_and_unchanged_initial_dirty_are_not_task_edits(self):
        self.write("app.py", "def public():\n    return 2\n")
        self.write("initial.txt", "existing work")
        start = capture_worktree(self.repo)
        prepared = prepare_files(self.repo, start, ["app.py"])
        result = verify_files(self.repo, start, prepared)
        self.assertEqual([], result["changed_paths"])
        self.assertTrue(result["manifest_matches"])
        self.assertFalse(result["semantic_reuse_approved"])
        self.assertEqual(4, start["cost"]["file_reads"])
        self.assertFalse(self.store.current.exists())

    def test_change_before_first_prepare_is_rejected(self):
        start = capture_worktree(self.repo)
        self.write("app.py", "def public():\n    return 2\n")
        with self.assertRaisesRegex(CapabilityError, "MODIFIED_BEFORE_PREPARE"):
            prepare_files(self.repo, start, ["app.py"])

    def test_scope_can_expand_before_new_file_edit_but_never_rewrite_initial_values(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        self.write("app.py", "def public():\n    return 2\n")
        expanded = prepare_files(self.repo, start, ["app.py", "next.py"], first)
        self.assertEqual(first["app.py"], expanded["app.py"])
        self.assertIsNone(expanded["next.py"])
        self.write("next.py", "def next_use():\n    return 3\n")
        result = verify_files(self.repo, start, expanded)
        self.assertEqual(["app.py", "next.py"], result["changed_paths"])
        self.assertFalse(result["manifest_matches"])

    def test_post_edit_scope_expansion_is_rejected(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        self.write("next.py", "new implementation")
        with self.assertRaisesRegex(CapabilityError, "MODIFIED_BEFORE_PREPARE"):
            prepare_files(self.repo, start, ["next.py"], first)

    def test_outside_scope_change_is_not_a_partial_success(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        self.write("unknown.py", "unexpected edit")
        with self.assertRaisesRegex(CapabilityError, "OUTSIDE_SCOPE"):
            verify_files(self.repo, start, first)

    def test_initial_dirty_reverted_to_head_is_detected_even_when_status_is_clean(self):
        self.write("app.py", "def public():\n    return 2\n")
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        fixtures.git(self.repo, "restore", "app.py")
        result = verify_files(self.repo, start, first)
        self.assertEqual({}, result["snapshot"]["status"])
        self.assertEqual(["app.py"], result["changed_paths"])

    def test_full_digest_detects_same_size_and_restored_mtime_after_receipt(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        before = (self.repo / "app.py").stat()
        self.write("app.py", "def public():\n    return 2\n")
        os.utime(self.repo / "app.py", ns=(before.st_atime_ns, before.st_mtime_ns))
        result = verify_files(self.repo, start, first)
        self.assertFalse(result["manifest_matches"])
        self.assertIn("app.py", result["changed_paths"])

    def test_deletion_and_new_file_absence_are_explicit(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py", "new file.py"])
        (self.repo / "app.py").unlink()
        self.write("new file.py", "created")
        result = verify_files(self.repo, start, first)
        self.assertIsNone(result["snapshot"]["files"]["app.py"])
        self.assertEqual(["app.py", "new file.py"], result["changed_paths"])

    def test_head_change_invalidates_baseline(self):
        start = capture_worktree(self.repo)
        first = prepare_files(self.repo, start, ["app.py"])
        fixtures.git(self.repo, "commit", "--allow-empty", "-qm", "changed base")
        with self.assertRaisesRegex(CapabilityError, "BASELINE_CHANGED"):
            verify_files(self.repo, start, first)

    def test_oversized_file_and_more_than_64_files_never_claim_coverage(self):
        self.write("large.txt", "x" * (128 * 1024 + 1))
        with self.assertRaisesRegex(CapabilityError, "TOO_LARGE"):
            capture_worktree(self.repo)
        (self.repo / "large.txt").unlink()
        for number in range(65):
            self.write(f"file{number}.txt", "small")
        with self.assertRaisesRegex(CapabilityError, "FILE_LIMIT"):
            capture_worktree(self.repo)

    def test_unreadable_and_sensitive_paths_do_not_emit_contents(self):
        self.write(".env", "PRIVATE_VALUE=not-for-output")
        with self.assertRaisesRegex(CapabilityError, "SENSITIVE_PATH") as failure:
            capture_worktree(self.repo)
        self.assertNotIn("PRIVATE_VALUE", str(failure.exception))
        (self.repo / ".env").unlink()
        with patch("cp_runtime.capability_index.bounded_read", side_effect=CapabilityError("UNREADABLE")):
            with self.assertRaisesRegex(CapabilityError, "UNREADABLE"):
                capture_worktree(self.repo, ["app.py"])

    def test_process_output_is_bounded_during_read_and_timeout_is_finite(self):
        with self.assertRaisesRegex(CapabilityError, "OUTPUT_LIMIT"):
            _bounded_process([sys.executable, "-c", "import sys; sys.stdout.write('x'*1000000)"],
                             self.repo, time.monotonic() + 3, 1024)
        began = time.monotonic()
        with self.assertRaisesRegex(CapabilityError, "DEADLINE"):
            _bounded_process([sys.executable, "-c", "import time; time.sleep(30)"],
                             self.repo, began + 0.3, 1024)
        self.assertLess(time.monotonic() - began, 2)

    def test_snapshot_schema_and_missing_observation_fail_closed(self):
        start = capture_worktree(self.repo, ["app.py"])
        wrong = copy.deepcopy(start)
        wrong["schema_version"] = True
        with self.assertRaises(CapabilityError):
            changed_paths(start, wrong)
        wrong = copy.deepcopy(start)
        wrong["files"] = {}
        with self.assertRaisesRegex(CapabilityError, "EVIDENCE_INCOMPLETE"):
            changed_paths(start, wrong)

    def test_status_paths_are_literal_and_a_rename_tracks_both_paths(self):
        fixtures.git(self.repo, "mv", "app.py", "with space[1].py")
        snapshot = capture_worktree(self.repo)
        self.assertEqual({"app.py", "with space[1].py"}, set(snapshot["status"]))
        self.assertIsNone(snapshot["files"]["app.py"])

    def test_git_status_race_during_capture_is_rejected(self):
        original = GitView.status
        calls = 0
        def changing(view):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.write("raced.py", "changed concurrently")
            return original(view)
        with patch.object(GitView, "status", changing):
            with self.assertRaisesRegex(CapabilityError, "BASELINE_CHANGED"):
                capture_worktree(self.repo, ["app.py"])

    def test_hidden_git_index_flags_cannot_hide_edits_before_preparation(self):
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                start = capture_worktree(self.repo)
                fixtures.git(self.repo, "update-index", "--" + flag, "app.py")
                self.write("app.py", "def public():\n    return 2\n")
                with self.assertRaisesRegex(CapabilityError, "INDEX_VISIBILITY_UNPROVEN"):
                    prepare_files(self.repo, start, ["app.py"])
                fixtures.git(self.repo, "update-index", "--no-" + flag, "app.py")
                fixtures.git(self.repo, "restore", "app.py")


if __name__ == "__main__":
    unittest.main()
