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
            "native_async_user_prompt_submit": {
                "status": "SUPPORTED",
                "evidence": "OFFICIAL_DOCS_CURRENT",
                "registration": "OPTIONAL_USER_PROMPT_SUBMIT",
            },
        }
        self.unknown = {
            "native_async_user_prompt_submit": {
                "status": "UNKNOWN",
                "evidence": "NOT_EVALUATED",
                "registration": "OPTIONAL_USER_PROMPT_SUBMIT",
            },
        }

    def test_supported_profile_emits_native_async_only_for_user_prompt(self) -> None:
        fragment = package_manager.hook_fragment(self.script, self.supported)
        user_hook = fragment["UserPromptSubmit"][0]["hooks"][0]
        self.assertIs(user_hook["async"], True)
        for event in ("PreToolUse", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "SessionEnd"):
            self.assertNotIn("async", fragment[event][0]["hooks"][0])

    def test_unknown_profile_omits_optional_hook_flag_and_preserves_events(self) -> None:
        fragment = package_manager.hook_fragment(self.script, self.unknown)
        self.assertNotIn("UserPromptSubmit", fragment)
        self.assertEqual(
            {"PreToolUse", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "SessionEnd"},
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
            "codex_version": "0.153.4",
            "codex_version_output": "codex-cli 0.153.4",
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


if __name__ == "__main__":
    unittest.main()
