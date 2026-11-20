"""中文：基础入口的首次安装、复跑与恢复边界。
English: First install, repeat entry and ownership-preserving recovery on both operating systems.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "codex-cross-project-engineering-assistant"
MARKET = "cp-assistant-base"


class BaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.home = self.base / ("账户 home" if os.name == "nt" else '账户 "home" \\path')
        self.home.mkdir()
        self.codex = self.home / ".codex"
        self.marker = self.base / "registered"
        self.failure = self.base / "remove-failure"
        self.output = self.base / "list.json"
        self.log = self.base / "actions.log"
        self.state = self.codex / "cp-assistant-base-state.json"
        self.market = self.home / ".agents/plugins/cp-assistant-base-marketplace"
        self.payload = self.market / "plugins" / PACKAGE
        host = self.base / ("component.cmd" if os.name == "nt" else "component")
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.codex),
            "CP_ASSISTANT_DESKTOP_COMPONENT": str(host),
            "BASE_TEST_MARK": str(self.marker),
            "BASE_TEST_FAIL": str(self.failure),
            "BASE_TEST_LIST": str(self.output),
            "BASE_TEST_LOG": str(self.log),
        }
        self.entry = (
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(ROOT / "scripts/cp-assistant.ps1"),
                "install-base",
            ]
            if os.name == "nt"
            else ["/bin/sh", str(ROOT / "scripts/cp-assistant.sh"), "install-base"]
        )
        if os.name == "nt":
            host.write_bytes(
                (
                    '@echo off\n>>"%BASE_TEST_LOG%" echo %*\n'
                    'if "%2"=="add" type nul > "%BASE_TEST_MARK%"\n'
                    'if "%2"=="remove" if exist "%BASE_TEST_FAIL%" exit /b 9\n'
                    'if "%2"=="remove" if exist "%BASE_TEST_MARK%" del "%BASE_TEST_MARK%"\n'
                    'if not "%2"=="list" exit /b 0\nif exist "%BASE_TEST_MARK%" goto registered\n'
                    'echo {"installed":[],"available":[]}\nexit /b 0\n:registered\ntype "%BASE_TEST_LIST%"\nexit /b 0\n'
                )
                .replace("\n", "\r\n")
                .encode("ascii")
            )
        else:
            host.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$BASE_TEST_LOG"\n'
                'case "$2" in\nadd) : > "$BASE_TEST_MARK" ;;\n'
                'remove) [ ! -e "$BASE_TEST_FAIL" ] || exit 9; rm -f "$BASE_TEST_MARK" ;;\n'
                'list) if [ -e "$BASE_TEST_MARK" ]; then cat "$BASE_TEST_LIST"; else printf \'%s\\n\' \'{"installed":[],"available":[]}\'; fi ;;\nesac\n',
                encoding="utf-8",
            )
            host.chmod(0o755)
        self.version = json.loads((ROOT / ".codex-plugin/plugin.json").read_bytes())["version"]
        self.record = dict(
            pluginId=PACKAGE + "@" + MARKET,
            name=PACKAGE,
            marketplaceName=MARKET,
            version=self.version,
            installed=True,
            enabled=True,
            installPolicy="AVAILABLE",
            authPolicy="ON_INSTALL",
        )
        self.wire(self.record)

    def wire(self, *rows):
        self.output.write_text(json.dumps({"installed": list(rows), "available": []}), encoding="ascii")

    def launch(self):
        return subprocess.run(self.entry, cwd=self.base, env=self.env, capture_output=True, timeout=90)

    def test_managed_rerun_only_reads_exact_registration_and_preserves_user_intent(self):
        first = self.launch()
        self.assertEqual(first.returncode, 0, first.stderr)
        state = json.loads(self.state.read_text(encoding="utf-8-sig"))
        self.assertEqual(state["market_root"], str(self.market))
        state.pop("status")
        self.state.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        original = self.state.read_bytes()
        for row, code in (
            (self.record, "ready"),
            ({**self.record, "enabled": False}, "DISABLED"),
            ({**self.record, "version": "1.0.0"}, "VERSION_MISMATCH"),
            ({**self.record, "installed": "true"}, "UNVERIFIED"),
        ):
            with self.subTest(code=code):
                self.wire(row)
                before = len(self.log.read_bytes().splitlines())
                p = self.launch()
                self.assertEqual(p.returncode == 0, code == "ready")
                self.assertIn(code.encode(), p.stdout + p.stderr)
                after = self.log.read_bytes().splitlines()[before:]
                self.assertEqual(len(after), 1)
                self.assertTrue(after[0].startswith(b"plugin list"))
                self.assertEqual(self.state.read_bytes(), original)

    def test_incomplete_cleanup_preserves_owned_transaction_and_unknown_target(self):
        self.wire({**self.record, "enabled": False})
        self.failure.touch()
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertEqual(json.loads(self.state.read_bytes())["status"], "RECOVERY_REQUIRED")
        inside = self.payload / "user-note.txt"
        inside.write_bytes(b"user-owned")
        sibling = self.market / "user-sibling.txt"
        sibling.write_bytes(b"other content")
        self.failure.unlink()
        self.wire(self.record)
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertEqual(inside.read_bytes(), b"user-owned")
        self.assertEqual(json.loads(self.state.read_bytes())["status"], "RECOVERY_REQUIRED")
        inside.rename(self.base / "preserved-note.txt")
        ok = self.launch()
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(sibling.read_bytes(), b"other content")
        self.assertEqual((self.base / "preserved-note.txt").read_bytes(), b"user-owned")
        self.assertEqual(json.loads(self.state.read_bytes())["status"], "INSTALLED")

    def test_ambiguous_fresh_registration_is_never_adopted(self):
        self.marker.touch()
        self.wire(self.record, self.record)
        p = self.launch()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"IDENTITY_CONFLICT", p.stdout + p.stderr)
        self.assertFalse(self.state.exists())
        self.assertTrue(self.marker.exists())

    @unittest.skipIf(os.name == "nt", "POSIX entry permissions")
    def test_nine_git_entry_modes_and_english_recovery_options(self):
        listing = subprocess.check_output(
            ["git", "ls-files", "--stage", "--", "scripts/*.sh"], cwd=ROOT, text=True
        ).splitlines()
        self.assertEqual(len(listing), 9)
        self.assertTrue(all(line.startswith("100755 ") for line in listing))
        for branch in (ROOT / "scripts", ROOT / "locales/en/scripts"):
            help_result = subprocess.run(
                ["sh", str(branch / "restore-latest-backup.sh"), "--help"], env=self.env, capture_output=True
            )
            # 中文：英语覆盖层以同一安装包脚本目录运行。 English: An overlay runs in its packaged script directory.
            if branch == ROOT / "scripts":
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
            rejected = subprocess.run(
                ["sh", str(branch / "restore-latest-backup.sh"), "--scope", "repo"],
                env=self.env,
                capture_output=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
