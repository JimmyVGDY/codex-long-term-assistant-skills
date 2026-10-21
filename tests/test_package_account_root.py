"""中文：显式账户目录必须与实际账户位置相同，不能扩大写入范围。
English: An explicit account directory must identify the existing account location, never broaden writes.
"""
import os
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from test_package_manager_security import package_manager as manager


class AccountRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / ".agents").mkdir()
        patch = mock.patch.object(manager.Path, "home", return_value=self.home)
        patch.start()
        self.addCleanup(patch.stop)

    def test_default_account_location_stays_unchanged(self):
        with mock.patch.dict(os.environ, {"CP_ASSISTANT_AGENTS_HOME": ""}):
            self.assertEqual(manager.user_skills_home(), self.home / ".agents/skills")

    def test_explicit_same_physical_root_is_used_for_all_account_targets(self):
        path = self.home / ".agents"
        with mock.patch.dict(os.environ, {"CP_ASSISTANT_AGENTS_HOME": str(path)}):
            self.assertEqual(manager.agents_home(), path)
            self.assertEqual(manager.plugin_marketplace_root(), path / "plugins/cp-assistant-marketplace")
            self.assertEqual(manager.base_marketplace_root(), path / "plugins/cp-assistant-base-marketplace")

    def test_foreign_relative_and_missing_override_are_rejected(self):
        foreign = self.home / "foreign"
        foreign.mkdir()
        for value in (str(foreign), ".agents", str(self.home / "missing")):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"CP_ASSISTANT_AGENTS_HOME": value}):
                with self.assertRaises(manager.InstallError):
                    manager.agents_home()

    def test_explicit_junction_target_preserves_descendant_link_rejection(self):
        original, target = self.home / ".agents", self.home / "physical-agents"
        original.rmdir()
        target.mkdir()
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(original), str(target)],
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.addCleanup(original.rmdir)
        else:
            original.symlink_to(target, target_is_directory=True)
            self.addCleanup(original.unlink)
        with mock.patch.dict(os.environ, {"CP_ASSISTANT_AGENTS_HOME": str(target)}):
            self.assertEqual(manager.agents_home(), target)
            manager.reject_link_ancestors(manager.user_skills_home())
            with self.assertRaises(manager.InstallError):
                manager.reject_link_ancestors(original / "skills")


if __name__ == "__main__":
    unittest.main()
