"""中文：预算根路径规范化必须保留跨阶段共享、真实短路径和项目隔离。

English: Budget-root normalization preserves shared stages, real short paths, and project isolation.
"""
from __future__ import annotations

import ctypes
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime.capability_gate_evidence import capture_worktree
from cp_runtime.capability_index import ReadBudget, scan


class CapabilityBudgetPathTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def assert_shared_budget(self, alias):
        budget = ReadBudget(alias)
        self.assertEqual(self.store.repo_path, budget.repo)
        before = capture_worktree(alias, ["app.py"], _budget=budget)
        after = scan(self.store, ["app.py"], _budget=budget)
        self.assertEqual(2, before["cost"]["file_reads"])
        self.assertEqual(3, after["cost"]["source_reads"])
        self.assertEqual(before["files"]["app.py"], self.store.read()["entries"][0]["file_sha256"])

    def test_equivalent_root_spelling_preserves_cross_stage_budget(self):
        self.assert_shared_budget(self.repo / ".." / "repo")

    @unittest.skipUnless(os.name == "nt", "Windows short-path API")
    def test_real_windows_short_alias_preserves_cross_stage_budget(self):
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(self.repo.resolve()), buffer, len(buffer))
        if not length:
            self.skipTest("Short-path names are unavailable on this filesystem")
        self.assertLess(length, len(buffer))
        alias = Path(buffer.value)
        if alias == self.repo.resolve():
            self.skipTest("This filesystem did not produce a distinct short alias")
        self.assert_shared_budget(alias)


if __name__ == "__main__":
    unittest.main()
