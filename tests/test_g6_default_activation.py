"""中文：新 Desktop 默认独立于历史 V3/V4 回放解析。

English: New Desktop default resolves separately from historical V3/V4 replay.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime.g6_default_activation import resolve
from cp_runtime.g6_flexible_policy import POLICY_ID


class G6DefaultActivationTests(unittest.TestCase):
    def test_unbound_new_task_uses_g6_without_qualification_cards(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary) / "plain-workspace"
            cwd.mkdir()
            with mock.patch.dict(os.environ, CODEX_HOME=str(Path(temporary) / "codex-home")):
                result = resolve(session_id="new-session", cwd=cwd)
            self.assertEqual(result["status"], "NEW_TASK_DEFAULT")
            self.assertEqual(result["policy_id"], POLICY_ID)

    def test_existing_research_head_keeps_historical_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary) / "plain-workspace"
            cwd.mkdir()
            old_head = Path(temporary) / "old-head.json"
            old_head.write_text("{}", encoding="utf8")
            with mock.patch.dict(os.environ, CODEX_HOME=str(Path(temporary) / "codex-home")), \
                 mock.patch("cp_runtime.research_campaign._head", return_value=old_head):
                result = resolve(session_id="old-session", cwd=cwd)
            self.assertEqual(result["status"], "LEGACY_ROOT_BOUND")
            self.assertIsNone(result["policy_id"])


if __name__ == "__main__":
    unittest.main()
