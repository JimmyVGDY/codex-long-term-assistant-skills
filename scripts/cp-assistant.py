#!/usr/bin/env python3
"""中文：保留调用者目录并复用现有命令的统一入口。

English: Unified entry reusing existing commands without changing the caller directory.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Sequence

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
    print("Codex 跨项目助手日常入口")
    print("Usage: cp-assistant <command> [options]")
    print("Commands: help, install-base, status, doctor, verify, inventory,")
    print("          install-enhancement, recover, resume")
    print("help and install-base do not require the enhancement runtime.")
    print("status, doctor, inventory and resume support --json; verify does not.")
    print("recover and install commands write managed installation state.")
    print("Use --help after a command for its options.")


def _entry(target: Path, arguments: Sequence[str]) -> int:
    previous_argv, previous_path = sys.argv, list(sys.path)
    previous_bytecode = sys.dont_write_bytecode
    sys.argv = [str(target), *arguments]
    sys.path.insert(0, str(target.parent))
    sys.dont_write_bytecode = True
    try:
        runpy.run_path(str(target), run_name="__main__")
        return 0
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(str(exc.code), file=sys.stderr)
        return 1
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode


def _line(value) -> str:
    return str(value).replace("\r", " ").replace("\n", " ")


def _render(data: dict) -> None:
    view = data.get("ux") if isinstance(data.get("ux"), dict) else data
    print("状态： " + _line(view.get("overall", "UNKNOWN")))
    if view.get("available"):
        print(_line(view["available"]))
    affected = view.get("affected") or []
    if affected:
        print("受影响： " + _line(", ".join(map(str, affected))))
    causes = view.get("cause") or []
    if causes:
        print("原因： " + _line("; ".join(str(item.get("detail", "")) for item in causes[:3])))
    action = view.get("next_action_detail") or {}
    next_action = action.get("display_command") or action.get("expected_result") or data.get("next_action")
    if next_action:
        print("下一步： " + _line(next_action))
    if "items" in data:
        print("受管条目： " + str(len(data["items"])))
    print("完整记录：使用 --json")


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"help", "--help", "-h"}:
        print_help()
        return 0
    command, remainder = arguments[0], arguments[1:]
    if command == "install-base":
        if remainder:
            if remainder in (["--help"], ["-h"]):
                print("Usage: cp-assistant install-base (writes the managed base installation)")
                return 0
            print("[ERROR] install-base does not accept extra arguments", file=sys.stderr)
            return 2
        if os.name == "nt":
            invocation = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                          "-File", str(ROOT / "scripts" / "install-base.ps1")]
        else:
            invocation = ["sh", str(ROOT / "scripts" / "install-base.sh")]
        return subprocess.run(invocation).returncode
    if command not in COMMANDS:
        print("[ERROR] unknown cp-assistant command: " + command, file=sys.stderr)
        return 2
    if sys.version_info < (3, 11):
        if "--json" in remainder:
            print(json.dumps({"schema": "cp-assistant/1", "overall": "UNKNOWN",
                              "reason": "PYTHON_REQUIRED", "next_action": "codex plugin list --json"}))
        else:
            print("Python 3.11+ is required for management commands.", file=sys.stderr)
        return 2
    if command == "install-enhancement":
        for position, item in enumerate(remainder):
            if item == "--scope" and position + 1 < len(remainder) and remainder[position + 1] != "user":
                print("[ERROR] install-enhancement requires --scope user", file=sys.stderr)
                return 2
            if item.startswith("--scope=") and item != "--scope=user":
                print("[ERROR] install-enhancement requires --scope user", file=sys.stderr)
                return 2
    target = COMMANDS[command]
    display = command in {"status", "doctor", "inventory"} and not any(
        item in remainder for item in ("--json", "--help", "-h", "--recover")
    )
    if not display:
        return _entry(ROOT / target[0], [*target[1:], *remainder])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = _entry(ROOT / target[0], [*target[1:], *remainder, "--json"])
    try:
        data = json.loads(output.getvalue())
        if not isinstance(data, dict):
            raise ValueError("object required")
    except ValueError:
        print(output.getvalue(), end="")
        return exit_code
    _render(data)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
