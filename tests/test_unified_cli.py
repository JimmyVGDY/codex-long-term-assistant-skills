from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UnifiedCliTests(unittest.TestCase):
    def test_python_help_is_local_and_does_not_need_state(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cp-assistant.py"), "--help"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("install-base", result.stdout)
        self.assertIn("resume", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Windows launcher regression")
    def test_powershell_help_does_not_require_python_manager(self) -> None:
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
             str(ROOT / "scripts" / "cp-assistant.ps1"), "--help"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("install-enhancement", result.stdout)

    def test_source_entry_uses_whitelisted_commands_without_shell(self) -> None:
        source = (ROOT / "scripts" / "cp-assistant.py").read_text(encoding="utf-8")
        self.assertIn("COMMANDS", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("eval(", source)
