#!/usr/bin/env python3
"""中文：白名单统一入口，兼容源码树和解压发行包。

English: Whitelisted unified entry compatible with source trees and extracted archives.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = {
    "status": ("scripts/package_manager.py", "status"),
    "doctor": ("scripts/package_manager.py", "doctor"),
    "verify": ("scripts/package_manager.py", "verify"),
    "inventory": ("scripts/package_manager.py", "inventory"),
    "install-enhancement": ("scripts/package_manager.py", "install", "--scope", "user", "--mode", "plugin"),
    "recover": ("scripts/package_manager.py", "recover"),
    "resume": ("scripts/cp-runtime.py", "project-resume"),
}


def print_help() -> None:
    print("Codex Cross Project Assistant daily entry")
    print("Usage: cp-assistant <command> [options]")
    print("Commands:")
    print("  help                 Show this help (no Python state access)")
    print("  install-base        Install the no-Python base Plugin")
    print("  status              Read-only status summary")
    print("  doctor              Read-only diagnostics")
    print("  verify              Verify an existing installation")
    print("  inventory           Read-only managed-file inventory")
    print("  install-enhancement Install the managed enhancement")
    print("  recover             Recover an unfinished install transaction")
    print("  resume              Read-only project recovery summary")
    print("Use --help after a command for that command's existing options.")


def _run(command: Sequence[str]) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(list(command), cwd=str(ROOT), env=env)
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"help", "--help", "-h"}:
        print_help()
        return 0
    command, remainder = args[0], args[1:]
    if command == "install-base":
        if os.name == "nt":
            return _run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                         str(ROOT / "scripts" / "install-base.ps1"), *remainder])
        return _run(["sh", str(ROOT / "scripts" / "install-base.sh"), *remainder])
    if command not in COMMANDS:
        print("[ERROR] unknown cp-assistant command: " + command, file=sys.stderr)
        print_help()
        return 2
    target = list(COMMANDS[command])
    return _run([sys.executable, "-B", str(ROOT / target[0]), *target[1:], *remainder])


if __name__ == "__main__":
    raise SystemExit(main())
