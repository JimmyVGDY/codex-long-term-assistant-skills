"""中文：从改动前冻结的 V2 字节验证历史读回与续写，夹具均为合成数据。

English: Replay and continue pre-change V2 byte fixtures; all identities are synthetic.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import delegation_budget as budget  # noqa: E402


class FrozenBudgetV2Tests(unittest.TestCase):
    def test_original_bytes_preserve_projection_and_writer_version(self):
        source = ROOT / "tests" / "fixtures" / "delegation-budget-v2"
        for name in ("active", "completed"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "budget.jsonl"
                shutil.copyfile(source / (name + "-v2.jsonl"), path)
                expected = json.loads((source / (name + "-expected.json")).read_text(encoding="utf-8"))
                before = path.read_bytes()
                self.assertEqual(expected, budget.read_budget(path))
                self.assertEqual(before, path.read_bytes())
                rid = next(iter(expected["reservations"]))
                if name == "active":
                    budget.mark_started(path, reservation_id=rid, agent_id="fixture-resumed-child")
                    budget.mark_completed(path, reservation_id=rid, outcome="PASS")
                state = budget.close_budget(path, conclusion="PASS")
                self.assertEqual("2.0", state["schema_version"])
                self.assertEqual(4, state["usage"]["units"])
                self.assertTrue(path.read_bytes().startswith(before))
                self.assertEqual({"2.0"}, {json.loads(line)["schema_version"]
                                          for line in path.read_text(encoding="utf-8").splitlines()})


if __name__ == "__main__":
    unittest.main()
