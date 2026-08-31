#!/usr/bin/env python3
"""V5.1 installer path, integrity and restore security tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "package_manager.py"


def run(args: list[str], env: dict[str, str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-B", str(MANAGER), *args],
        env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"unexpected rc={result.returncode}, expected={expected}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


class PackageManagerSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="package-manager-v5-")
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.codex = self.home / ".codex"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_install_verify_idempotent_and_restore_integrity(self) -> None:
        run(["install", "--dry-run"], self.env)
        run(["install"], self.env)
        run(["verify"], self.env)
        run(["install"], self.env)
        run(["verify"], self.env)
        state = json.loads((self.codex / ".cross-project-assistant-install.json").read_text(encoding="utf-8"))
        backup = Path(state["backup"])
        manifest = json.loads((backup / "backup-manifest.json").read_text(encoding="utf-8"))
        existing = next(record for record in manifest["records"] if record.get("existed"))
        payload = backup / existing["backup_relative"]
        if payload.is_dir():
            file_to_tamper = next(path for path in payload.rglob("*") if path.is_file())
        else:
            file_to_tamper = payload
        file_to_tamper.write_bytes(file_to_tamper.read_bytes() + b"\ntampered\n")
        failed = run(["restore", "--backup", str(backup)], self.env, expected=1)
        self.assertIn("完整性校验失败", failed.stderr)
        run(["verify"], self.env)

    def test_source_tree_and_symlink_targets_are_rejected(self) -> None:
        bad_env = {**self.env, "CODEX_HOME": str(ROOT)}
        result = run(["install", "--dry-run"], bad_env, expected=1)
        self.assertTrue("危险目录" in result.stderr or "源码目录" in result.stderr)

        self.codex.mkdir(parents=True)
        outside = self.home / "outside-agents"
        outside.mkdir()
        (self.codex / "agents").symlink_to(outside, target_is_directory=True)
        result = run(["install", "--component", "agents"], self.env, expected=1)
        self.assertIn("符号链接", result.stderr)


if __name__ == "__main__":
    unittest.main()
