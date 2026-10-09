"""中文：安装器消费载荷读回，同时保留缺少复审的状态。

English: Installer consumes payload readback while retaining missing review status.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import package_manager  # noqa: E402


class G6PackageDeliveryTests(unittest.TestCase):
    def test_three_way_readback_is_installed_not_runtime_effect(self):
        report = {"payload_digest": "a" * 64, "file_count": 320}
        result = package_manager.g6_install_delivery_report(report, report, report)
        self.assertEqual(result["status"], "INSTALLED_READBACK_VERIFIED")
        self.assertTrue(result["installed_readback_verified"])
        self.assertFalse(result["independent_review_verified"])
        self.assertFalse(result["repair_review_verified"])
        self.assertEqual(result["next_action"], "report_distinct_runtime_effect")

    def test_mismatched_cache_digest_restricts_install(self):
        report = {"payload_digest": "a" * 64}
        with self.assertRaisesRegex(package_manager.InstallError, "G6_INSTALL_PAYLOAD_READBACK_MISMATCH"):
            package_manager.g6_install_delivery_report(report, report, {"payload_digest": "b" * 64})


if __name__ == "__main__":
    unittest.main()
