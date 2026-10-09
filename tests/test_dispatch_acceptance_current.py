"""中文：验收夹具不污染账户，且坏响应不冒充放行。

English: Acceptance fixtures isolate account state and never classify malformed output as allow.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_acceptance():
    spec = importlib.util.spec_from_file_location("current_dispatch_acceptance", ROOT / "scripts/dispatch-policy-acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CurrentDispatchAcceptanceTests(unittest.TestCase):
    def test_malformed_output_is_not_allow(self):
        module = load_acceptance()
        self.assertEqual(module.observed_permission("not-json"), "invalid-output")
        self.assertEqual(module.observed_permission('{"ok": false}'), "invalid-output")
        self.assertEqual(module.observed_permission("{}"), "allow")

    def test_missing_evidence_default_uses_temporary_account(self):
        module = load_acceptance()
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / "real-account"
            account.mkdir()
            marker = account / "sentinel.txt"
            marker.write_text("unchanged", encoding="utf-8")
            with patch.dict(os.environ, {"CODEX_HOME": str(account)}):
                result = module.current_case("isolation-check", "gpt-6-sol", "medium", "worker", "allow", direct_choice=False)
            self.assertTrue(result["pass"], result)
            self.assertEqual([p.name for p in account.iterdir()], ["sentinel.txt"])
            self.assertEqual(marker.read_text(encoding="utf-8"), "unchanged")

    def test_old_worker_tuple_contract_remains_explicit(self):
        module = load_acceptance()
        self.assertTrue(module.legacy_case("legacy-terra", "gpt-5.6-terra", "high", "worker", "allow")["pass"])
        self.assertTrue(module.legacy_case("legacy-sol", "gpt-5.6-sol", "high", "worker", "deny")["pass"])
        self.assertTrue(module.legacy_case("legacy-implicit", "", "", "cp_review_data_contract", "deny")["pass"])


if __name__ == "__main__":
    unittest.main()
