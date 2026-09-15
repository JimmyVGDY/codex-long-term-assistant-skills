from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
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


    @contextlib.contextmanager
    def installed_fixture(self, mode="plugin", include_base=True):
        from payload_integrity import write_manifest
        home, skills = self.base / "codex", self.base / "user-skills"
        cache = home / "plugins" / "cache" / package_manager.MARKETPLACE / package_manager.PACKAGE / package_manager.VERSION
        for name in (".codex-plugin", "skills", "hooks", "runtime"):
            (cache / name).mkdir(parents=True)
        for name in package_manager.skill_names():
            directory = cache / "skills" / name if mode == "plugin" else skills / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "SKILL.md").write_text("fixture", encoding="utf-8")
        for relative in ("tools/cp-runtime.py", "tools/evolution.py",
                         "cp-assistant-hooks/cp_hook.py", "cp-assistant-hooks/cp_gate.py"):
            target = home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        for agent in package_manager.agent_files():
            target = home / "agents" / agent.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        runtime = home / "runtime" / "cp_runtime"
        runtime.mkdir(parents=True)
        (runtime / "cli.py").write_text("fixture", encoding="utf-8")
        payload = write_manifest(cache, package_manager.PACKAGE, package_manager.VERSION)
        state = {"schema_version": 3, "package": package_manager.PACKAGE,
                 "version": package_manager.VERSION, "mode": mode,
                 "components": {"enhancement": {"status": "MANAGED"}},
                 "payload_identity": {"cache_digest": payload["payload_digest"],
                                      "marketplace_digest": payload["payload_digest"]},
                 "managed_hashes": {str(runtime): package_manager.tree_sha256(runtime)}}
        if include_base:
            state["components"]["base"] = {"status": "PLUGIN_MANAGED" if mode == "plugin" else "STANDALONE_SKILLS"}
        state_file = home / "cp-assistant-v6-state.json"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        native = {"checked": True, "base": None, "enhancement": {
            "installed": True, "enabled": True, "version": package_manager.VERSION,
        }}
        with contextlib.ExitStack() as stack:
            for patcher in (
                mock.patch.object(package_manager, "codex_home", return_value=home),
                mock.patch.object(package_manager, "user_skills_home", return_value=skills),
                mock.patch.object(package_manager, "plugin_marketplace_payload", return_value=cache),
                mock.patch.object(package_manager, "_codex_available", return_value=mode == "plugin"),
                mock.patch.object(package_manager, "_codex_executable", return_value="codex"),
                mock.patch.object(package_manager, "_probe_plugin_host", return_value={"registrations": native}),
                mock.patch.object(package_manager, "_host_compatibility_status", return_value={"compatible": True}),
                mock.patch.object(package_manager, "payload_report", return_value={"file_count": 236}),
            ):
                stack.enter_context(patcher)
            yield state_file

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

    def test_doctor_summary_answers_available_impact_and_next_action(self):
        data = {
            "scope": "user", "mode": "plugin",
            "checks": [{"id": "plugin", "status": "WARN"}],
            "plugin_activation": {"active": True, "checked": True},
            "base_activation": {"active": True, "checked": True},
            "state": {"components": {"base": {"status": "PLUGIN_MANAGED"}}},
            "remediation": ["运行 verify 并读回 Plugin installed/enabled/version。"],
        }
        summary = package_manager.doctor_summary(data)
        self.assertEqual(("DEGRADED", ["plugin"]), (summary["overall"], summary["affected"]))
        self.assertEqual(summary["ux"]["available"], summary["available"])
        self.assertEqual(summary["ux"]["next_action_detail"]["display_command"], summary["next_action"])
        self.assertEqual("ux-summary/1", summary["ux"]["schema"])
        self.assertEqual("VERIFY_INSTALLATION", summary["ux"]["next_action_detail"]["code"])
        self.assertNotIn("--json", summary["ux"]["next_action_detail"]["argv"])

    def test_status_summary_keeps_base_available_when_enhancement_is_missing(self):
        summary = package_manager.status_summary({
            "scope": "user", "mode": "plugin", "plugin_activation": {"active": True},
            "base_activation": {"active": True, "checked": True},
            "state": {"components": {"base": {"status": "PLUGIN_MANAGED"}}},
        })
        self.assertEqual("PASS", summary["overall"])
        self.assertEqual("基础模式正常；已安装增强能力按实际状态显示", summary["available"])
        self.assertEqual([], summary["affected"])
        self.assertEqual("NOT_ENABLED", next(item for item in summary["ux"]["capabilities"]
                                               if item["id"] == "enhancement")["availability"])

    def test_status_summary_marks_host_drift_and_missing_enhancement(self):
        summary = package_manager.status_summary({
            "scope": "user", "mode": "plugin", "plugin_activation": {"active": True},
            "base_activation": {"active": True, "checked": True},
            "host_compatibility": {"compatible": False, "status": "HOST_DRIFT_REINSTALL_REQUIRED"},
            "state": {"components": {"enhancement": {"status": "MANAGED"}}},
        })
        self.assertEqual(["enhancement"], summary["affected"])
        self.assertEqual("HOST_DRIFT_REINSTALL_REQUIRED", summary["cause"][0]["detail"])

    def test_status_marks_migrated_base_active_for_managed_enhancement(self):
        output = io.StringIO()
        with self.installed_fixture(), contextlib.redirect_stdout(output):
            package_manager.status("user", "plugin", None, summary=False)
        value = json.loads(output.getvalue())
        self.assertTrue(value["base_activation"]["active"])
        self.assertEqual("PASS", value["ux"]["overall"])

    def test_base_only_native_facts_pass_doctor_and_distinguish_disabled_unknown_and_duplicate(self):
        with self.installed_fixture() as path:
            path.unlink()
            cache = package_manager.codex_home() / "plugins" / "cache" / package_manager.BASE_MARKETPLACE / package_manager.PACKAGE / package_manager.VERSION
            shutil.copytree(package_manager.plugin_cache_root() / "skills", cache / "skills")
            package_manager.base_state_path().write_text(json.dumps({
                "schema_version": 1, "package": package_manager.PACKAGE,
                "marketplace": package_manager.BASE_MARKETPLACE,
                "market_root": str(package_manager.base_marketplace_root()), "status": "INSTALLED",
            }), encoding="utf-8")
            base = {"installed": True, "enabled": True, "version": package_manager.VERSION,
                    "plugin_id": package_manager.PACKAGE + "@" + package_manager.BASE_MARKETPLACE}
            registered = {"checked": True, "base": base, "enhancement": None}
            before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
            with mock.patch.object(package_manager, "_probe_plugin_host", return_value={"registrations": registered}):
                value = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertTrue(package_manager.doctor(False, "user", None))
                self.assertEqual("PASS", json.loads(output.getvalue())["overall"])
            self.assertEqual("PASS", value["overall"])
            self.assertEqual("NOT_ENABLED", next(row for row in value["capabilities"] if row["id"] == "enhancement")["availability"])
            for record, expected in (
                ({"checked": True, "base": {**base, "enabled": False}, "enhancement": None}, "UNAVAILABLE"),
                ({"checked": False, "base": None, "enhancement": None}, "UNKNOWN"),
            ):
                with mock.patch.object(package_manager, "_probe_plugin_host", return_value={"registrations": record}):
                    value = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
                self.assertEqual(expected, next(row for row in value["capabilities"] if row["id"] == "base-plugin")["availability"])
            with mock.patch.object(package_manager, "_probe_plugin_host", return_value={"registrations": {**registered, "enhancement": base}}):
                value = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
            self.assertEqual("ERROR", value["overall"])
            self.assertIn("plugin-registration", value["affected"])
            self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_base_activation_requires_explicit_managed_ownership(self):
        self.assertFalse(package_manager._base_capability_active(
            True, "plugin", {}, {}, True, False,
        ))
        self.assertTrue(package_manager._base_capability_active(
            True, "plugin", {}, {"components": {"base": {"status": "PLUGIN_MANAGED"}}}, True, False,
        ))
        self.assertTrue(package_manager._base_capability_active(
            True, "standalone", {}, {"components": {"base": {"status": "STANDALONE_SKILLS"}}}, False, False,
        ))
        self.assertTrue(package_manager._base_capability_active(
            False, "standalone", {}, {"components": {"base": {"status": "STANDALONE_SKILLS"}}}, False, False,
        ))

    def test_required_budget_missing_keeps_base_available_but_blocks_delegation(self):
        with self.installed_fixture(), mock.patch.dict(os.environ, {"CP_DELEGATION_BUDGET_REQUIRED": "1", "CP_DELEGATION_BUDGET_PATH": ""}):
            view = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
        self.assertEqual("ERROR", view["overall"])
        capabilities = {row["id"]: row for row in view["capabilities"]}
        self.assertEqual("AVAILABLE", capabilities["base-plugin"]["availability"])
        self.assertEqual("BLOCKED", capabilities["delegation-budget"]["availability"])
        self.assertEqual("RESTORE_CONTROL_PREREQUISITES", view["next_action_detail"]["code"])

    def test_live_transaction_precedes_blocked_control_without_recovery_write(self):
        with self.installed_fixture(), mock.patch.dict(os.environ, {"CP_DELEGATION_BUDGET_REQUIRED": "1", "CP_DELEGATION_BUDGET_PATH": ""}):
            journal = package_manager.transaction_path("user")
            journal.write_text(json.dumps({"schema_version": 1, "scope": "user", "stage": "PREPARED"}), encoding="utf-8")
            before = journal.read_bytes()
            view = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
            self.assertEqual(before, journal.read_bytes())
        self.assertEqual("ERROR", view["overall"])
        self.assertEqual("RECOVER_INSTALLATION_TRANSACTION", view["next_action_detail"]["code"])
        self.assertEqual("WRITE", view["next_action_detail"]["action_kind"])
        self.assertIn("recover", view["next_action_detail"]["argv"])
        self.assertEqual("BLOCKED", next(row for row in view["capabilities"] if row["id"] == "delegation-budget")["availability"])

    def test_changed_read_error_is_retried_and_repeated_change_is_unstable(self):
        with self.installed_fixture() as state_path:
            original = package_manager._diagnostic_object
            count = 0
            def read(path):
                nonlocal count
                if path == state_path:
                    count += 1
                    return ({}, "STATE_UNREADABLE_OR_INVALID") if count % 2 else ({}, None)
                return original(path)
            with mock.patch.object(package_manager, "_diagnostic_object", side_effect=read):
                data = package_manager._diagnostic_facts("user", None, None)
        self.assertEqual(4, count)
        self.assertEqual("INSTALLATION_CHANGED_DURING_READ", data["sample_error"])
        self.assertFalse(data["base_activation"]["checked"])

    def test_stable_semantic_state_error_does_not_become_read_instability(self):
        with self.installed_fixture() as path:
            state = json.loads(path.read_bytes())
            state["schema_version"] = 999
            path.write_text(json.dumps(state), encoding="utf-8")
            data = package_manager._diagnostic_facts("user", None, None)
        self.assertEqual("INSTALLATION_STATE_IDENTITY_INVALID", data["state_error"])
        self.assertNotIn("sample_error", data)

    def test_transaction_changes_are_rechecked_before_projecting_availability(self):
        with self.installed_fixture(), mock.patch.object(package_manager, "_diagnostic_journal", side_effect=[
            (None, None), ({"stage": "PREPARED"}, None),
            (None, None), ({"stage": "APPLYING"}, None),
        ]):
            data = package_manager._diagnostic_facts("user", None, None)
        self.assertEqual("INSTALLATION_CHANGED_DURING_READ", data["sample_error"])
        self.assertEqual("DEGRADED", package_manager._ux_summary(data)["overall"])

    def test_oversized_transaction_is_bounded_and_never_recovered_by_diagnostics(self):
        with self.installed_fixture():
            journal = package_manager.transaction_path("user")
            journal.write_bytes(b" " * (8 * 1024 * 1024 + 1))
            with mock.patch.object(package_manager, "_load_live_journal", side_effect=AssertionError("unbounded reader")):
                data = package_manager._diagnostic_facts("user", None, None)
            self.assertEqual(8 * 1024 * 1024 + 1, journal.stat().st_size)
        self.assertEqual("TRANSACTION_UNREADABLE", data["transaction_error"])

    def test_empty_journal_object_remains_invalid(self):
        with self.installed_fixture():
            package_manager.transaction_path("user").write_text("{}", encoding="utf-8")
            data = package_manager._diagnostic_facts("user", None, None)
        self.assertEqual("TRANSACTION_UNREADABLE", data["transaction_error"])

    def test_explicit_gate_without_enhancement_is_fail_closed_without_state_writes(self):
        from cp_runtime.project import onboard_project
        from cp_runtime.capability_store import CapabilityStore
        from cp_runtime.capability_gate import GatePolicy
        repo = self.repo()
        profile = onboard_project(repo, "UX-CONTROL", "Fixture", self.base / "context")
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.base / "empty-home")}), \
                mock.patch.object(package_manager, "codex_home", return_value=self.base / "empty-home"), \
                mock.patch.object(package_manager, "_codex_available", return_value=False):
            policy = GatePolicy(CapabilityStore(profile.profile_path, repo))
            policy.set_enabled(True, None)
            before = {str(path): path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
            value = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, str(repo), str(profile.profile_path)))
            after = {str(path): path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual("BLOCKED", next(row for row in value["capabilities"] if row["id"] == "controlled-write")["availability"])
        self.assertEqual(before, after)

    def test_inventory_corrupt_state_returns_structured_error_without_repair(self):
        repo = self.repo()
        path = package_manager.state_path("repo", repo)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"not-json")
        value = package_manager.inventory("repo", "standalone", str(repo))
        self.assertEqual("ERROR", value["overall"])
        self.assertFalse(value["delete_authorized"])
        self.assertEqual(b"not-json", path.read_bytes())

    def test_native_and_state_version_conflict_cannot_pass(self):
        with self.installed_fixture() as path:
            value = json.loads(path.read_text(encoding="utf-8"))
            value["version"] = "7.9.2"
            path.write_text(json.dumps(value), encoding="utf-8")
            view = package_manager._ux_summary(package_manager._diagnostic_facts("user", None, None))
        self.assertEqual("ERROR", view["overall"])
        self.assertTrue(any("INSTALLATION_VERSION_CONFLICT" in item["detail"] for item in view["cause"]))

    def test_payload_detail_remains_available_in_detailed_status(self):
        with self.installed_fixture():
            view = package_manager._diagnostic_facts("user", None, None)
        self.assertEqual({"source", "marketplace", "cache"}, set(view["payload_identity"]))
        self.assertEqual(view["state"]["payload_identity"]["cache_digest"], view["payload_identity"]["cache"]["payload_digest"])

    def test_status_uses_persisted_mode_when_mode_is_not_supplied(self):
        output = io.StringIO()
        with self.installed_fixture("standalone"), contextlib.redirect_stdout(output):
            package_manager.status("user", None, None, summary=False)
        value = json.loads(output.getvalue())
        self.assertEqual("standalone", value["mode"])
        self.assertEqual("PASS", value["ux"]["overall"])

    def test_invalid_persisted_mode_fails_closed_in_status_and_doctor(self):
        with self.installed_fixture() as path:
            state = json.loads(path.read_text(encoding="utf-8"))
            state["mode"] = "legacy"
            path.write_text(json.dumps(state), encoding="utf-8")
            for call in (
                lambda: package_manager.status("user", None, None, summary=False),
                lambda: package_manager.doctor(False, "user", None, summary=False),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    call()
                value = json.loads(output.getvalue())
                self.assertEqual("INVALID_PERSISTED_MODE", value["mode_error"])
                self.assertEqual("ERROR", value["ux"]["overall"])

    def test_doctor_matches_status_for_migrated_base(self):
        outputs = []
        with self.installed_fixture():
            for call in (
                lambda: package_manager.status("user", None, None, summary=False),
                lambda: package_manager.doctor(False, "user", None, summary=False),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    call()
                outputs.append(json.loads(output.getvalue()))
        self.assertTrue(outputs[1]["base_activation"]["active"])
        self.assertEqual("PASS", outputs[0]["ux"]["overall"])
        self.assertEqual(outputs[0]["ux"]["overall"], outputs[1]["overall"])

    def test_doctor_rejects_enhancement_without_managed_base(self):
        output = io.StringIO()
        with self.installed_fixture(include_base=False), contextlib.redirect_stdout(output):
            package_manager.doctor(False, "user", None, summary=False)
        value = json.loads(output.getvalue())
        self.assertFalse(value["base_activation"]["active"])
        self.assertEqual("ERROR", next(item for item in value["checks"] if item["id"] == "plugin")["status"])
        self.assertEqual("ERROR", value["overall"])
        self.assertEqual(value["overall"], value["ux"]["overall"])

    def test_doctor_accepts_standalone_base_without_codex_host(self):
        output = io.StringIO()
        with self.installed_fixture("standalone"), contextlib.redirect_stdout(output):
            package_manager.doctor(False, "user", None, summary=False)
        value = json.loads(output.getvalue())
        self.assertEqual("standalone", value["mode"])
        self.assertTrue(value["base_activation"]["active"])
        self.assertEqual("PASS", value["overall"])
        self.assertEqual(value["overall"], value["ux"]["overall"])

    def test_status_summary_marks_uninstalled_base_as_unavailable(self):
        summary = package_manager.status_summary({
            "scope": "user", "mode": "plugin",
            "plugin_activation": {"active": False, "checked": True, "detail": "not installed"},
            "base_activation": {"active": False, "checked": True, "detail": "not installed"},
            "state": {},
        })
        self.assertEqual("ERROR", summary["overall"])
        self.assertEqual("UNAVAILABLE", next(item for item in summary["ux"]["capabilities"]
                                               if item["id"] == "base-plugin")["availability"])

    def test_status_summary_action_is_structured_and_scoped(self):
        summary = package_manager.status_summary({
            "scope": "user", "mode": "plugin", "plugin_activation": {"active": False, "checked": True},
            "base_activation": {"active": False, "checked": True}, "state": {},
        })
        action = summary["ux"]["next_action_detail"]
        self.assertEqual(("CHECK_PLUGIN_REGISTRATION", "READ_ONLY", "USER"),
                         (action["code"], action["action_kind"], action["scope"]))
        self.assertEqual(["codex", "plugin", "list", "--json"], action["argv"])

    def test_enhancement_activation_does_not_prove_base_activation(self):
        summary = package_manager.status_summary({
            "scope": "user", "mode": "plugin",
            "plugin_activation": {"active": True, "checked": True},
            "base_activation": {"active": False, "checked": True},
            "state": {},
        })
        self.assertEqual("UNAVAILABLE", next(item for item in summary["ux"]["capabilities"]
                                               if item["id"] == "base-plugin")["availability"])

    def test_doctor_summary_never_masks_error_check(self):
        summary = package_manager.doctor_summary({
            "scope": "user", "mode": "plugin",
            "checks": [{"id": "payload", "status": "ERROR", "detail": "broken"}],
            "remediation": ["重新下载并校验当前发行包。"],
            "plugin_activation": {"active": True, "checked": True},
            "base_activation": {"active": True, "checked": True},
            "state": {"components": {"base": {"status": "PLUGIN_MANAGED"}}},
        })
        self.assertEqual("ERROR", summary["overall"])
        self.assertEqual(["payload"], summary["affected"])
        self.assertEqual("ERROR", summary["ux"]["overall"])

    def test_status_json_keeps_mode_for_the_default_summary_projection(self):
        output = io.StringIO()
        with mock.patch.object(package_manager, "codex_home", return_value=self.base / "codex"), \
                mock.patch.object(package_manager, "_codex_available", return_value=False), \
                contextlib.redirect_stdout(output):
            package_manager.status("user", "standalone", None, summary=False)
        self.assertEqual("standalone", json.loads(output.getvalue())["mode"])

    @unittest.skipUnless(os.name == "nt", "PowerShell launcher regression")
    def test_windows_doctor_launcher_checks_actual_python_and_runs(self):
        directory = self.base / "plain"
        directory.mkdir()
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(ROOT / "scripts" / "doctor.ps1"), "--json", "--scope", "repo", "--repo-path", str(directory)],
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
