"""中文：真实子进程预算与输出隔离回归。 English: Real subprocess budgets and output isolation."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp_runtime.resume_snapshot import SnapshotBudget, _bounded_process


class ResumeResourcesTests(unittest.TestCase):
    def test_stderr_is_not_part_of_snapshot_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = SnapshotBudget(timeout=5, byte_limit=1000)
            output, code, complete = _bounded_process(
                [sys.executable, "-c", "import sys; print('data'); print('warning', file=sys.stderr)"],
                Path(directory), budget)
        self.assertEqual(0, code)
        self.assertTrue(complete)
        self.assertEqual(b"data", output.strip())
        self.assertLess(budget.remaining, 1000 - len(output))

    def test_output_budget_stops_and_reaps_process(self):
        processes = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        with tempfile.TemporaryDirectory() as directory, mock.patch("subprocess.Popen", side_effect=start):
            budget = SnapshotBudget(timeout=5, byte_limit=128)
            output, code, complete = _bounded_process(
                [sys.executable, "-c", "import sys; sys.stdout.write('x'*1000000); sys.stdout.flush()"],
                Path(directory), budget)
        self.assertFalse(complete)
        self.assertLessEqual(len(output), 128)
        self.assertIsNotNone(processes[0].poll())

    def test_timeout_with_inherited_child_pipe_remains_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            output, code, complete = _bounded_process(
                [sys.executable, "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); time.sleep(20)"],
                Path(directory), SnapshotBudget(timeout=0.2, byte_limit=1024))
            elapsed = time.monotonic() - started
        self.assertFalse(complete)
        self.assertLess(elapsed, 3)
