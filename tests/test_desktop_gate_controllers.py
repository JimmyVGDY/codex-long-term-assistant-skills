"""中文：新执行阶段和安装注册的端到端契约边界。

English: Contract boundaries for new workflow stages and installer registrations.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))
import package_manager
from cp_runtime.gate_contract import registration_inventory


def controller():
    path = ROOT / "skills/engineering-quality-delivery/scripts/execution_guard.py"
    spec = importlib.util.spec_from_file_location("gate_execution_controller", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesktopGateControllerTests(unittest.TestCase):
    def test_installer_generated_rules_have_all_actual_entrypoints(self):
        profile = {"native_async_user_prompt_submit": {
            "status": "SUPPORTED", "evidence": "OFFICIAL_DOCS_CURRENT"}}
        fragment = package_manager.hook_fragment(ROOT / "hooks/cp_hook.py", profile)
        rows = registration_inventory(fragment)
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["entrypoint"] for row in rows},
                         {"cp_hook.py", "cp_gate.py", "cp_context.py"})
        changed = json.loads(json.dumps(fragment))
        changed["PreToolUse"][0]["hooks"][0]["command"] = "python future_guard.py"
        with self.assertRaisesRegex(ValueError, "UNMAPPED_MANAGED_GATE_ENTRYPOINT"):
            registration_inventory(changed)

    def test_missing_review_allows_stage_without_fabricating_a_pass(self):
        module = controller()
        state = {"phase": "PLAN", "profile": "STRICT", "completed_gates": [],
                 "required_gates": ["preimplementation_review"], "history": [],
                 "authorization": {"deploy": False}}
        args = type("Args", (), {"state_dir": str(ROOT), "to": "IMPLEMENT", "note": ""})()
        with mock.patch.object(module, "load_state", return_value=state), \
                mock.patch.object(module, "validate_project_context"), \
                mock.patch.object(module, "save_state"), contextlib.redirect_stdout(io.StringIO()):
            module.command_transition(args)
        self.assertEqual(state["phase"], "IMPLEMENT")
        self.assertEqual(state["completed_gates"], [])
        self.assertEqual(state["gate_decisions"]["workflow_stage"]["verification_state"], "UNVERIFIED")
        self.assertEqual(state["authorization"], {"deploy": False})

    def test_new_envelope_uses_g6_and_explicit_legacy_stays_legacy(self):
        module = controller()
        for policy, expected in [(None, "g6-sol-medium"), ("reviewer-matrix-v3", "luna-low")]:
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as temporary:
                state_dir = Path(temporary) / "state"
                args = ["execution_guard.py", "init", "--state-dir", str(state_dir),
                        "--repo-path", str(ROOT), "--task-id", "test-new-envelope"]
                if policy:
                    args += ["--reviewer-policy", policy]
                fingerprint = {"repo_path": str(ROOT), "sha256": "a" * 64,
                               "untracked_sha256": "b" * 64}
                with mock.patch.object(sys, "argv", args), \
                        mock.patch.object(module, "capture_repo_fingerprint", return_value=fingerprint), \
                        contextlib.redirect_stdout(io.StringIO()):
                    module.main()
                state = json.loads((state_dir / "execution-state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["routing"]["model_profile"], expected)
                self.assertEqual(state["routing"]["delegation_budget"]["default_model_profile"], expected)


if __name__ == "__main__":
    unittest.main()


class InstalledGateRootTests(unittest.TestCase):
    def test_account_entry_uses_only_state_bound_cache(self):
        import importlib.util
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            hook_path = home / "cp-assistant-hooks/cp_gate.py"
            hook_path.parent.mkdir()
            hook_path.write_bytes((ROOT / "hooks/cp_gate.py").read_bytes())
            spec = importlib.util.spec_from_file_location("installed_gate_fixture", hook_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cache = home / "plugins/cache/cp-assistant-local/codex-cross-project-engineering-assistant/7.16.0"
            (cache / ".codex-plugin").mkdir(parents=True)
            (cache / ".codex-plugin/plugin.json").write_text(json.dumps({"name": "codex-cross-project-engineering-assistant", "version": "7.16.0"}), encoding="utf8")
            state = home / "cp-assistant-v6-state.json"
            state.write_text(json.dumps({"mode": "plugin", "version": "7.16.0"}), encoding="utf8")
            environment = dict(os.environ, CODEX_HOME=str(home))
            environment.pop("PLUGIN_ROOT", None)
            with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(module, "ROOT", home):
                self.assertEqual(module._runtime_root(), cache.resolve())
                (cache / ".codex-plugin/plugin.json").write_text(json.dumps({"name": "codex-cross-project-engineering-assistant", "version": "7.15.3"}), encoding="utf8")
                with self.assertRaisesRegex(ValueError, "GATE_RUNTIME_ENTRY_UNAVAILABLE"):
                    module._runtime_root()
                state.write_text(json.dumps({"mode": "plugin", "version": "../other"}), encoding="utf8")
                with self.assertRaisesRegex(ValueError, "GATE_RUNTIME_ENTRY_UNAVAILABLE"):
                    module._runtime_root()
