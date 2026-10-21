"""中文：安装恢复保留历史错误并核验原缓存，拒绝新漂移。
English: Preserve recovery history, verify original cache bytes and reject new drift.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from test_package_manager_security import package_manager as manager


class RecoveryRetryTests(unittest.TestCase):
    def test_successful_retry_preserves_prior_errors_as_history(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = {"stage": "RECOVERY_REQUIRED", "rollback_errors": ["prior failure"],
                       "errors": [], "mode": "standalone", "records": [], "backup": directory,
                       "journal_path": str(Path(directory) / "journal.json")}
            with mock.patch.object(manager, "_load_live_journal", return_value=journal), \
                    mock.patch.object(manager, "_journal_write"), mock.patch.object(manager, "_finish_journal"):
                manager.recover_transaction("user")
            self.assertEqual(journal["rollback_errors"], [])
            self.assertEqual(journal["recovery_attempts"][0]["previous_errors"], ["prior failure"])

    def test_original_cache_recovery_requires_exact_backup_and_known_current_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            home, market, backup = base / "home", base / "market", base / "backup"
            market.mkdir()
            backup.mkdir()
            (market / "module.py").write_bytes(b"original module")
            (backup / "module.py").write_bytes(b"original module")
            (backup / "cache.bin").write_bytes(b"original cache bytes")
            with mock.patch.object(manager, "codex_home", return_value=home), \
                    mock.patch.object(manager, "plugin_marketplace_payload", return_value=market):
                cache = manager.plugin_cache_root("7.17.1")
                cache.mkdir(parents=True)
                (cache / "module.py").write_bytes(b"original module")
                original = manager.tree_sha256(backup)
                previous = {"version": "7.17.1", "cache_path": str(cache), "cache_tree_sha256": original}
                (cache / "unknown.txt").write_bytes(b"preserve unknown change")
                before = manager.tree_sha256(cache)
                with self.assertRaisesRegex(manager.InstallError, "PREVIOUS_CACHE_CURRENT_DRIFT"):
                    manager._restore_previous_cache(previous, str(backup))
                self.assertEqual(manager.tree_sha256(cache), before)
                (cache / "unknown.txt").unlink()
                with self.assertRaisesRegex(manager.InstallError, "PREVIOUS_CACHE_BACKUP_MISMATCH"):
                    manager._restore_previous_cache(previous, str(market))
                manager._restore_previous_cache(previous, str(backup))
                self.assertEqual(manager.tree_sha256(cache), original)
                self.assertEqual(manager.tree_sha256(backup), original)
                manager.remove_path(cache)
                manager._restore_previous_cache(previous, str(backup))
                self.assertEqual(manager.tree_sha256(cache), original)


if __name__ == "__main__":
    unittest.main()
