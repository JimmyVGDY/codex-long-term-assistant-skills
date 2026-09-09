"""中文：组合门禁操作共享原预算，旧扫描和查询接口保持原行为。

English: Composed gate operations share original budgets; legacy scan/query behavior remains.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import capability_index as index
from cp_runtime.capability_gate_evidence import capture_worktree
from cp_runtime.capability_store import CapabilityError


class CapabilityGateBudgetTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def test_scan_and_query_share_reads_and_query_still_has_zero_writes(self):
        budget = index.ReadBudget(self.repo)
        scanned = index.scan(self.store, ["app.py"], _budget=budget)
        before = self.store.current.read_bytes()
        queried = index.query(self.store, "public", _budget=budget)
        self.assertEqual(2, scanned["cost"]["source_reads"])
        self.assertEqual(3, queried["cost"]["source_reads"])
        self.assertEqual(before, self.store.current.read_bytes())
        self.assertEqual(1, len(queried["candidates"]))

    def test_repeated_verification_cannot_reset_read_or_byte_budget(self):
        budget = index.ReadBudget(self.repo)
        size = (self.repo / "app.py").stat().st_size
        with patch.object(index, "MAX_READS", 3), patch.object(index, "MAX_READ_BYTES", 3 * size):
            index.scan(self.store, ["app.py"], _budget=budget)
            index.query(self.store, "public", _budget=budget)
            with self.assertRaisesRegex(CapabilityError, "BUDGET"):
                index.query(self.store, "public", _budget=budget)
            self.assertEqual(3, budget.reads)
            self.assertEqual(3 * size, budget.bytes_read)

    def test_additional_file_reserves_final_reread_of_all_previously_observed_files(self):
        budget = index.ReadBudget(self.repo)
        budget.read("app.py")
        budget.verify()
        (self.repo / "other.py").write_text("def other():\n    return 2\n", encoding="utf-8")
        with patch.object(index, "MAX_READS", 4):
            with self.assertRaisesRegex(CapabilityError, "BUDGET"):
                budget.read("other.py")
        self.assertEqual(2, budget.reads)
        self.assertNotIn("other.py", budget.observed)

    def test_cached_source_is_reverified_after_scan_before_query_returns(self):
        budget = index.ReadBudget(self.repo)
        index.scan(self.store, ["app.py"], _budget=budget)
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        with self.assertRaisesRegex(CapabilityError, "CHANGED"):
            index.query(self.store, "public", _budget=budget)

    def test_git_capture_and_index_scan_share_the_same_file_read_limit(self):
        budget = index.ReadBudget(self.repo)
        first = capture_worktree(self.repo, ["app.py"], _budget=budget)
        second = index.scan(self.store, ["app.py"], _budget=budget)
        self.assertEqual(2, first["cost"]["file_reads"])
        self.assertEqual(3, second["cost"]["source_reads"])

    def test_budget_from_other_repository_is_rejected(self):
        budget = index.ReadBudget(self.base)
        with self.assertRaisesRegex(CapabilityError, "BUDGET_IDENTITY_MISMATCH"):
            index.scan(self.store, ["app.py"], _budget=budget)
        self.assertFalse(self.store.current.exists())


if __name__ == "__main__":
    unittest.main()
