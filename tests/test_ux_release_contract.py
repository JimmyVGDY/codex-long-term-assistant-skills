"""中文：P1 状态聚合与动作合同的发行回归。

English: Release regressions for P1 status aggregation and action contracts.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_manager


class StatusReleaseContractTests(unittest.TestCase):
    def test_doctor_cannot_report_pass_when_installation_identity_is_invalid(self):
        result = package_manager.doctor_summary({
            "scope": "user", "mode": "plugin", "mode_error": "INVALID_PERSISTED_MODE",
            "checks": [],
        })
        self.assertEqual("ERROR", result["overall"])
        self.assertEqual(result["overall"], result["ux"]["overall"])

    def test_unknown_selected_enhancement_prevents_overall_pass(self):
        result = package_manager.status_summary({
            "scope": "user", "mode": "plugin",
            "base_activation": {"active": True, "checked": True},
            "plugin_activation": {"active": True, "checked": True},
            "state": {"components": {"enhancement": {"status": "CORRUPT"}}},
        })
        self.assertEqual("DEGRADED", result["overall"])
        self.assertIn("enhancement", result["affected"])


if __name__ == "__main__":
    unittest.main()
