"""中文：桌面组件的契约探针；伪进程不证明实机加载。

English: Desktop component contract probes; fake processes do not prove loading.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import desktop_host
import package_manager as manager
from codex_compatibility import CompatibilityError


class DesktopHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.component = self.directory / "desktop-component"
        self.component.write_bytes(b"synthetic Desktop component")
        self.env = patch.dict(os.environ, {"CP_ASSISTANT_DESKTOP_COMPONENT": str(self.component)})
        self.env.start()
        self.fixture = json.loads((ROOT / "tests/fixtures/codex-cli-help-v1.json").read_text(encoding="utf-8"))
        self.calls = []
        self.changed_help = False
        self.version = "codex-cli 0.155.0-alpha.16"

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def run_component(self, args, **kwargs):
        self.calls.append(args)
        if args == ["--version"]:
            text = self.version
        elif args[:2] == ["plugin", "list"]:
            self.assertEqual(5, len(args))
            self.assertEqual("--marketplace", args[2])
            self.assertIn(args[3], {manager.MARKETPLACE, manager.BASE_MARKETPLACE})
            text = '{"installed":[],"available":[]}'
        else:
            key = "marketplace_" + args[2] if args[1] == "marketplace" else "plugin_" + args[1]
            text = zlib.decompress(base64.b64decode(self.fixture[key])).decode("utf-8")
            if self.changed_help:
                text += "\nnew incompatible command option"
        return subprocess.CompletedProcess(args, 0, text, "")

    def test_internal_prerelease_is_not_rejected_as_a_standalone_cli_version(self):
        with patch.object(manager, "_run_codex", side_effect=self.run_component):
            value = manager._probe_plugin_host()
        self.assertTrue(value["ok"])
        self.assertEqual(desktop_host.SCHEMA, value["registry_schema"])
        self.assertEqual("0.155.0-alpha.16", value["codex_version"])
        self.assertTrue(manager._validate_host_binding(manager._host_binding(value)))
        self.assertEqual(str(self.component.resolve()), manager._codex_executable())
        self.assertNotIn(["plugin", "list", "--json"], self.calls)

    def test_changed_component_commands_fail_before_installation(self):
        self.changed_help = True
        with patch.object(manager, "_run_codex", side_effect=self.run_component):
            value = manager._probe_plugin_host()
            self.assertFalse(value["ok"])
            self.assertEqual(4, len(value["command_contract_errors"]))
            with self.assertRaises(manager.InstallError):
                manager._require_plugin_host()

    def test_corrupt_saved_binding_cannot_claim_current_desktop_compatibility(self):
        with patch.object(manager, "_run_codex", side_effect=self.run_component):
            value = manager._probe_plugin_host()
        binding = manager._host_binding(value)
        for key in ("registry_digest", "capability_digest", "hook_profile"):
            changed = copy.deepcopy(binding)
            changed[key] = "unknown"
            self.assertFalse(manager._validate_host_binding(changed))

    def test_invalid_explicit_component_does_not_fall_back_to_path_cli(self):
        with patch.dict(os.environ, {"CP_ASSISTANT_DESKTOP_COMPONENT": str(self.directory / "missing")}):
            with self.assertRaisesRegex(CompatibilityError, "COMPONENT_NOT_FOUND"):
                manager._codex_executable()
            self.assertFalse(manager._codex_available())


if __name__ == "__main__":
    unittest.main()
