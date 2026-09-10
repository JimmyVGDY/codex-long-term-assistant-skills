#!/usr/bin/env python3
"""中文：安装器按宿主证据生成可选 native async Hook 的定向测试。

English: Focused installer tests for evidence-bound optional native async Hooks.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("package_manager_under_test", ROOT / "scripts" / "package_manager.py")
assert spec and spec.loader
package_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_manager)


class NativeAsyncHookRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = ROOT / "cp-assistant-hooks" / "cp_hook.py"
        self.supported = {
            "apply_patch_result_profile": "result-v153",
            "native_async_user_prompt_submit": {
                "status": "SUPPORTED",
                "evidence": "OFFICIAL_DOCS_CURRENT",
                "registration": "OPTIONAL_USER_PROMPT_SUBMIT",
            },
            "native_apply_patch_operation": {
                "status": "SUPPORTED",
                "evidence": "OFFICIAL_SOURCE_TAG",
                "registration": "REQUIRED_APPLY_PATCH_PRE_POST",
            },
        }
        self.unknown = {
            "apply_patch_result_profile": "result-v153",
            "native_async_user_prompt_submit": {
                "status": "UNKNOWN",
                "evidence": "NOT_EVALUATED",
                "registration": "OPTIONAL_USER_PROMPT_SUBMIT",
            },
            "native_apply_patch_operation": {
                "status": "UNKNOWN",
                "evidence": "NOT_EVALUATED",
                "registration": "REQUIRED_APPLY_PATCH_PRE_POST",
            },
        }

    def test_supported_profile_emits_native_async_only_for_user_prompt(self) -> None:
        fragment = package_manager.hook_fragment(self.script, self.supported)
        user_hook = fragment["UserPromptSubmit"][0]["hooks"][0]
        self.assertIs(user_hook["async"], True)
        for event in ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "SessionEnd"):
            self.assertNotIn("async", fragment[event][0]["hooks"][0])
        self.assertEqual("apply_patch|Edit|Write", fragment["PostToolUse"][0]["matcher"])
        self.assertEqual(["Agent|spawn_agent", "apply_patch|Edit|Write"],
                         [entry["matcher"] for entry in fragment["PreToolUse"]])
        self.assertIn("cp_gate.py", fragment["PreToolUse"][1]["hooks"][0]["command"])
        self.assertIn("cp_gate.py", fragment["PostToolUse"][0]["hooks"][0]["command"])

    def test_unknown_profile_omits_optional_hook_flag_and_preserves_events(self) -> None:
        fragment = package_manager.hook_fragment(self.script, self.unknown)
        self.assertNotIn("UserPromptSubmit", fragment)
        self.assertEqual(
            {"PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "SessionEnd"},
            set(fragment),
        )

    def test_merge_hooks_reinstall_does_not_duplicate_managed_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-native-async-hooks-") as td:
            path = Path(td) / "hooks.json"
            path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "external"}]}]}},), encoding="utf-8")
            package_manager.merge_hooks(path, self.script, self.supported)
            package_manager.merge_hooks(path, self.script, self.unknown)
            hooks = json.loads(path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual([], hooks.get("UserPromptSubmit", []))
            self.assertEqual("external", hooks["Stop"][0]["hooks"][0]["command"])

    def test_plugin_preflight_rejects_frozen_version_with_unknown_async_capability(self) -> None:
        probe = {
            "version_ok": True,
            "codex_version": "0.154.0",
            "codex_version_output": "codex-cli 0.154.0",
            "version_contract_ok": True,
            "command_contract_errors": [],
            "plugin_list_json": True,
            "commands": {name: {"ok": True} for name in (
                "marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove",
            )},
        }
        with mock.patch.object(package_manager, "_probe_plugin_host", return_value=probe), \
             mock.patch.object(package_manager, "profile_for_version", return_value=self.unknown), \
             mock.patch.object(package_manager, "_isolated_plugin_preflight") as isolated:
            with self.assertRaisesRegex(package_manager.InstallError, "缺少已验证的 UserPromptSubmit async 能力"):
                package_manager._require_plugin_host()
        isolated.assert_not_called()

    def test_plugin_preflight_rejects_unknown_apply_patch_operation_contract(self) -> None:
        probe = {
            "version_ok": True,
            "codex_version": "0.154.0",
            "codex_version_output": "codex-cli 0.154.0",
            "version_contract_ok": True,
            "command_contract_errors": [],
            "plugin_list_json": True,
            "commands": {name: {"ok": True} for name in (
                "marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove",
            )},
        }
        profile = dict(self.supported)
        profile["native_apply_patch_operation"] = self.unknown["native_apply_patch_operation"]
        with mock.patch.object(package_manager, "_probe_plugin_host", return_value=probe), \
             mock.patch.object(package_manager, "profile_for_version", return_value=profile), \
             mock.patch.object(package_manager, "_isolated_plugin_preflight") as isolated:
            with self.assertRaisesRegex(package_manager.InstallError, "缺少已验证的 apply_patch Pre/Post 能力"):
                package_manager._require_plugin_host()
        isolated.assert_not_called()


if __name__ == "__main__":
    unittest.main()
