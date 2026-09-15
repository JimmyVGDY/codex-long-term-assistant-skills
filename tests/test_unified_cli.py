from __future__ import annotations

import subprocess
import os
import sys
import json
import tempfile
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

    def test_default_repository_scope_uses_callers_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "caller space O'Brien $ literal"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            command = [sys.executable, str(ROOT / "scripts" / "cp-assistant.py"), "inventory", "--scope", "repo", "--json"]
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(repo.resolve(), Path(json.loads(result.stdout)["base_path"]).resolve())

    @unittest.skipUnless(sys.platform == "win32", "Windows native arguments")
    def test_powershell_preserves_explicit_path_and_help_does_not_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "space O'Brien $ literal"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            launcher = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts" / "cp-assistant.ps1")]
            result = subprocess.run([*launcher, "inventory", "--scope", "repo", "--repo-path", str(repo), "--json"],
                                    cwd=root, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(repo.resolve(), Path(json.loads(result.stdout)["base_path"]).resolve())
            environment = dict(os.environ, CP_ASSISTANT_PYTHON=str(root / "missing-python"), CODEX_HOME=str(root / "no-install"))
            help_result = subprocess.run([*launcher, "install-base", "--help"], env=environment,
                                         capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, help_result.returncode, help_result.stderr)
            self.assertFalse((root / "no-install").exists())
            missing = subprocess.run([*launcher, "status", "--json"], env=environment,
                                     capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(2, missing.returncode)
            self.assertEqual("PYTHON_REQUIRED", json.loads(missing.stdout)["reason"])

    @unittest.skipIf(sys.platform == "win32", "POSIX native arguments")
    def test_posix_rejects_old_interpreter_and_keeps_help_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            interpreter = root / "old python"
            interpreter.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
            interpreter.chmod(0o755)
            env = dict(os.environ, CP_ASSISTANT_PYTHON=str(interpreter), CODEX_HOME=str(root / "no-install"))
            launcher = ["sh", str(ROOT / "scripts" / "cp-assistant.sh")]
            missing = subprocess.run([*launcher, "status", "--json"], env=env, capture_output=True, text=True)
            self.assertEqual(2, missing.returncode)
            self.assertEqual("PYTHON_REQUIRED", json.loads(missing.stdout)["reason"])
            help_result = subprocess.run([*launcher, "install-base", "--help"], env=env, capture_output=True, text=True)
            self.assertEqual(0, help_result.returncode)
            self.assertFalse((root / "no-install").exists())
