from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "package_manager.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("package_manager_ux_under_test", MANAGER)
assert SPEC and SPEC.loader
package_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_manager)


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


class PackageManagerUxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="package-ux-")
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def repo(self):
        path = self.base / "repo"
        path.mkdir()
        git(path, "init", "-q")
        git(path, "config", "user.name", "Test")
        git(path, "config", "user.email", "test@example.invalid")
        (path / "file.txt").write_text("one\n", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-qm", "fixture")
        return path

    def test_python_preflight_precedes_local_imports_and_version_comes_from_manifest(self):
        text = MANAGER.read_text(encoding="utf-8")
        self.assertLess(text.index("MINIMUM_PYTHON = (3, 11)"), text.index("from codex_compatibility import"))
        self.assertIn("VERSION = release_version()", text)
        self.assertNotIn('VERSION = "7.8.1"', text)
        self.assertEqual(json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"],
                         package_manager.VERSION)

    def test_windows_launchers_validate_actual_version_instead_of_directory_name(self):
        helper = (ROOT / "scripts" / "python-launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("sys.version_info >= (3, 11)", helper)
        for name in ("cp_hook.cmd", "cp_gate.cmd"):
            launcher = (ROOT / "hooks" / name).read_text(encoding="utf-8")
            self.assertIn("sys.version_info >= (3, 11)", launcher)
            self.assertIn("Python 3.11+", launcher)

    def test_non_git_inventory_is_read_only_basic_guidance(self):
        directory = self.base / "plain"
        directory.mkdir()
        before = sorted(path.relative_to(directory) for path in directory.rglob("*"))
        result = package_manager.inventory("repo", "standalone", str(directory))
        after = sorted(path.relative_to(directory) for path in directory.rglob("*"))
        self.assertEqual(before, after)
        self.assertEqual(("BASIC_ONLY", False, False),
                         (result["overall"], result["git_repository"], result["delete_authorized"]))
        cli = subprocess.run([sys.executable, str(MANAGER), "inventory", "--scope", "repo",
                              "--mode", "standalone", "--repo-path", str(directory)],
                             cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual("BASIC_ONLY", json.loads(cli.stdout)["overall"])

    def test_stateless_uninstall_preview_deletes_nothing_and_real_uninstall_refuses(self):
        repo = self.repo()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            package_manager.uninstall("repo", "standalone", str(repo), False, True)
        preview = json.loads(output.getvalue())
        self.assertEqual([], preview["will_delete"])
        self.assertEqual("REFUSED_WITHOUT_STATE", preview["real_uninstall"])
        self.assertFalse((repo / ".codex").exists())
        with self.assertRaisesRegex(package_manager.InstallError, "拒绝无状态卸载"):
            package_manager.uninstall("repo", "standalone", str(repo), False, False)

    def test_inventory_distinguishes_managed_missing_and_drift(self):
        repo = self.repo()
        state_path = repo / ".codex" / "cp-assistant-v6-state.json"
        state_path.parent.mkdir()
        target = repo / "file.txt"
        expected = package_manager.tree_sha256(target)
        state_path.write_text(json.dumps({"managed_hashes": {str(target): expected}}), encoding="utf-8")
        managed = package_manager.inventory("repo", "standalone", str(repo))
        self.assertEqual("MANAGED", managed["items"][0]["status"])
        target.write_text("two\n", encoding="utf-8")
        drift = package_manager.inventory("repo", "standalone", str(repo))
        self.assertEqual(("DEGRADED", "DRIFT"), (drift["overall"], drift["items"][0]["status"]))
        target.unlink()
        missing = package_manager.inventory("repo", "standalone", str(repo))
        self.assertEqual("MISSING", missing["items"][0]["status"])

    @unittest.skipUnless(os.name == "nt", "Windows path alias regression")
    def test_inventory_accepts_extended_length_alias_inside_repo(self):
        repo = self.repo()
        state_path = repo / ".codex" / "cp-assistant-v6-state.json"
        state_path.parent.mkdir()
        target = repo / "file.txt"
        extended_target = Path("\\\\?\\" + str(target))
        state_path.write_text(json.dumps({
            "managed_hashes": {str(extended_target): package_manager.tree_sha256(target)},
        }), encoding="utf-8")

        result = package_manager.inventory("repo", "standalone", str(repo))

        self.assertEqual("MANAGED", result["items"][0]["status"], result)

    def test_inventory_does_not_read_state_path_outside_managed_root(self):
        repo = self.repo()
        state_path = repo / ".codex" / "cp-assistant-v6-state.json"
        state_path.parent.mkdir()
        outside = self.base / "outside-secret.txt"
        outside.write_text("do-not-read\n", encoding="utf-8")
        state_path.write_text(json.dumps({"managed_hashes": {str(outside): "0" * 64}}), encoding="utf-8")
        original = package_manager.tree_sha256

        def guarded(path):
            self.assertNotEqual(outside, Path(path))
            return original(path)

        with mock.patch.object(package_manager, "tree_sha256", side_effect=guarded):
            result = package_manager.inventory("repo", "standalone", str(repo))
        self.assertEqual(("ERROR", "UNSAFE_PATH"), (result["overall"], result["items"][0]["status"]))

    def test_user_inventory_hashes_only_the_managed_global_block(self):
        fake_codex = self.base / "codex"
        fake_skills = self.base / "skills"
        fake_market = self.base / "marketplace"
        agents = fake_codex / "AGENTS.md"
        agents.parent.mkdir(parents=True)
        agents.write_text(package_manager.managed_global_text("user-owned prefix"), encoding="utf-8")
        expected = package_manager.tree_sha256(ROOT / "global" / "AGENTS.md")
        state = fake_codex / "cp-assistant-v6-state.json"
        state.write_text(json.dumps({"managed_hashes": {str(agents): expected}}), encoding="utf-8")

        with mock.patch.object(package_manager, "codex_home", return_value=fake_codex), \
                mock.patch.object(package_manager, "user_skills_home", return_value=fake_skills), \
                mock.patch.object(package_manager, "plugin_marketplace_root", return_value=fake_market):
            initial = package_manager.inventory("user", "plugin", None)
            agents.write_text(
                package_manager.managed_global_text("changed user-owned prefix"), encoding="utf-8"
            )
            user_edit = package_manager.inventory("user", "plugin", None)
            agents.write_text(
                agents.read_text(encoding="utf-8").replace("## 9. 交付表达", "## 9. 漂移"),
                encoding="utf-8",
            )
            managed_edit = package_manager.inventory("user", "plugin", None)

        self.assertEqual(("PASS", "MANAGED"), (initial["overall"], initial["items"][0]["status"]))
        self.assertEqual(("PASS", "MANAGED"), (user_edit["overall"], user_edit["items"][0]["status"]))
        self.assertEqual(("DEGRADED", "DRIFT"),
                         (managed_edit["overall"], managed_edit["items"][0]["status"]))

    def test_legacy_preference_classification_is_explicit_and_never_authorizes(self):
        cases = [
            ({"schema_version": 3, "package": package_manager.PACKAGE, "version": version}, "DEFAULT_OFF", "AUTO")
            for version in ("7.6.0", "7.6.1", "7.6.2", "7.7.0", "7.7.1")
        ] + [
            ({"capability_preference": {"source": "USER", "mode": "OFF"}}, "USER_OFF", "OFF"),
            ({"capability_preference": {"source": "MANAGED", "mode": "ON"}}, "LEGACY_ON", "AUTO"),
            ({"gate": {"enabled": True}}, "UNKNOWN_OFF", "OFF"),
        ]
        for state, classification, mode in cases:
            with self.subTest(classification=classification, state=state):
                result = package_manager.capability_preference_migration(state)
                self.assertEqual((classification, mode), (result["classification"], result["configured_mode"]))
                self.assertFalse(result["authorization"])
                self.assertFalse(result["scan_consent"])
                self.assertTrue(result["gate_policy_excluded"])

    def test_repo_upgrade_preview_includes_lazy_cas_preference_plan(self):
        repo = self.repo()
        state_path = repo / ".codex" / "cp-assistant-v6-state.json"
        state_path.parent.mkdir()
        state_path.write_text(json.dumps({"schema_version": 3, "package": package_manager.PACKAGE,
                                          "version": "7.6.2", "scope": "repo", "mode": "standalone",
                                          "managed_hashes": {}}), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            package_manager.install_repo(str(repo), True)
        preview = json.loads(output.getvalue())
        migration = preview["preference_migration"]
        self.assertEqual(("DEFAULT_OFF", "AUTO", "PROJECT_LAZY_CAS_AFTER_IDENTITY_BINDING"),
                         (migration["classification"], migration["configured_mode"], migration["application"]))

    def test_doctor_preserves_fields_and_adds_feature_checks_and_remediation(self):
        directory = self.base / "plain"
        directory.mkdir()
        output = io.StringIO()
        with mock.patch.object(package_manager, "payload_report", return_value={"file_count": 1, "payload_digest": "a" * 64}), \
                mock.patch.object(package_manager, "_codex_available", return_value=False), \
                contextlib.redirect_stdout(output):
            ok = package_manager.doctor(False, "repo", str(directory))
        result = json.loads(output.getvalue())
        self.assertTrue(ok)
        for old_field in ("package", "version", "python", "git", "plugin_manifest", "hooks_manifest"):
            self.assertIn(old_field, result)
        self.assertIn(result["overall"], {"PASS", "DEGRADED"})
        self.assertTrue(result["base_capabilities_available"])
        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual("NOT_APPLICABLE", checks["git"]["status"])
        self.assertIn("child-agent-policy", checks)
        self.assertIn("controlled-write", checks)

    def test_doctor_strict_projection_fails_degraded_state_but_recover_alias_is_shared(self):
        fake_home = self.base / "codex"
        output = io.StringIO()
        with mock.patch.object(package_manager, "codex_home", return_value=fake_home), \
                mock.patch.object(package_manager, "payload_report", return_value={"file_count": 1, "payload_digest": "a" * 64}), \
                mock.patch.object(package_manager, "_codex_available", return_value=False), \
                contextlib.redirect_stdout(output):
            strict_ok = package_manager.doctor(False, "user", None)
        self.assertFalse(strict_ok)
        self.assertEqual("DEGRADED", json.loads(output.getvalue())["overall"])
        with mock.patch.object(package_manager, "recover_transaction") as recover:
            self.assertTrue(package_manager.doctor(True, "user", None))
        recover.assert_called_once_with("user", None)

    @unittest.skipUnless(os.name == "nt", "PowerShell launcher regression")
    def test_windows_doctor_launcher_checks_actual_python_and_runs(self):
        directory = self.base / "plain"
        directory.mkdir()
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(ROOT / "scripts" / "doctor.ps1"), "--scope", "repo", "--repo-path", str(directory)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"python_version"', result.stdout)

    @unittest.skipUnless(os.name == "nt", "Windows Hook launcher regression")
    def test_windows_hook_launchers_execute_with_validated_python(self):
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.base),
                              "session_id": "session", "turn_id": "turn", "task_id": "turn"})
        environment = {**os.environ, "PLUGIN_ROOT": str(ROOT), "CODEX_HOME": str(self.base / "codex")}
        for name in ("cp_hook.cmd", "cp_gate.cmd"):
            with self.subTest(name=name):
                result = subprocess.run(["cmd.exe", "/d", "/c", str(ROOT / "hooks" / name), "Stop"],
                                        input=payload, env=environment, cwd=ROOT, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=15)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual({}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
