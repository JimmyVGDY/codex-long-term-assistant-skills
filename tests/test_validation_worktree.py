from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validation_worktree", ROOT / "scripts" / "validation_worktree.py")
assert SPEC and SPEC.loader
validation_worktree = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation_worktree)


class ValidationWorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-validation-worktree-")
        self.repo = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_dirty_baseline_is_allowed_when_validation_adds_no_change(self) -> None:
        (self.repo / "tracked.txt").write_text("already dirty\n", encoding="utf-8")
        before = validation_worktree.capture_worktree(self.repo)
        after = validation_worktree.capture_worktree(self.repo)
        validation_worktree.assert_worktree_unchanged(before, after)

    def test_new_untracked_artifact_fails_the_gate(self) -> None:
        before = validation_worktree.capture_worktree(self.repo)
        (self.repo / "cp-assistant-v6.lock").write_text("lock", encoding="utf-8")
        after = validation_worktree.capture_worktree(self.repo)
        with self.assertRaisesRegex(validation_worktree.WorktreeMutationError,
                                    "cp-assistant-v6.lock"):
            validation_worktree.assert_worktree_unchanged(before, after)

    def test_second_change_to_already_dirty_file_fails_the_gate(self) -> None:
        (self.repo / "tracked.txt").write_text("already dirty\n", encoding="utf-8")
        before = validation_worktree.capture_worktree(self.repo)
        (self.repo / "tracked.txt").write_text("changed again\n", encoding="utf-8")
        after = validation_worktree.capture_worktree(self.repo)
        with self.assertRaisesRegex(validation_worktree.WorktreeMutationError,
                                    "Git-visible worktree"):
            validation_worktree.assert_worktree_unchanged(before, after)

    def test_interrupt_still_runs_gate_and_preserves_original_failure(self) -> None:
        def interrupted() -> None:
            (self.repo / "tracked.txt").write_text("changed by validation\n", encoding="utf-8")
            raise KeyboardInterrupt("cancelled")

        with self.assertRaises(validation_worktree.WorktreeMutationError) as raised:
            validation_worktree.run_with_worktree_guard(self.repo, interrupted)
        self.assertIsInstance(raised.exception.__cause__, KeyboardInterrupt)

    def test_interrupt_is_reraised_when_worktree_is_unchanged(self) -> None:
        def interrupted() -> None:
            raise KeyboardInterrupt("cancelled")

        with self.assertRaisesRegex(KeyboardInterrupt, "cancelled"):
            validation_worktree.run_with_worktree_guard(self.repo, interrupted)

    def test_deleted_tracked_file_is_reported_as_worktree_mutation(self) -> None:
        def delete_tracked() -> None:
            (self.repo / "tracked.txt").unlink()

        with self.assertRaises(validation_worktree.WorktreeMutationError) as raised:
            validation_worktree.run_with_worktree_guard(self.repo, delete_tracked)
        self.assertNotIsInstance(raised.exception, FileNotFoundError)

    def test_validation_output_must_be_outside_worktree(self) -> None:
        with self.assertRaisesRegex(validation_worktree.WorktreeMutationError,
                                    "--output must be outside"):
            validation_worktree.require_output_outside_worktree(
                self.repo, self.repo / "validation.json"
            )
        external = self.repo.parent / "validation.json"
        self.assertEqual(
            external.resolve(),
            validation_worktree.require_output_outside_worktree(self.repo, external),
        )


if __name__ == "__main__":
    unittest.main()
