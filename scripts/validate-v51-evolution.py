#!/usr/bin/env python3
"""V5.1 自观察与受控自进化专项校验。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.cp_runtime.evolution.contracts import ExecutionAuthorization, EvolutionPolicy  # noqa: E402
from runtime.cp_runtime.evolution.cli import build_parser  # noqa: E402


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> int:
    evolution_dirs = [p for p in ROOT.rglob("evolution") if p.is_dir() and p.parent.name == "cp_runtime"]
    if len(evolution_dirs) != 1:
        fail("必须且只能存在一个 runtime/cp_runtime/evolution 权威实现，实际 %d 个" % len(evolution_dirs))
    expected = ROOT / "runtime" / "cp_runtime" / "evolution"
    if evolution_dirs[0].resolve() != expected.resolve():
        fail("受控自进化权威实现路径不正确")

    manifest = json.loads((expected / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "5.1.0":
        fail("evolution manifest 版本不是 5.1.0")
    if manifest.get("execution_authorization") != "NONE" or manifest.get("automatic_execution") is not False:
        fail("受控自进化边界被破坏")
    if ExecutionAuthorization.__members__ != {"NONE": ExecutionAuthorization.NONE}:
        fail("ExecutionAuthorization 只能包含 NONE")

    policy_raw = json.loads((ROOT / "config" / "evolution-policy.json").read_text(encoding="utf-8"))
    EvolutionPolicy.from_mapping(policy_raw)

    parser = build_parser()
    help_text = parser.format_help().lower()
    if "execute" in {action.dest.lower() for action in parser._actions}:
        fail("CLI 不得暴露 execute 参数")
    # 子命令必须显式固定，禁止出现 apply/execute/autofix。
    subcommands = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            subcommands.update(choices.keys())
    forbidden = {"execute", "apply", "autofix", "self-modify", "auto-accept"}
    if subcommands & forbidden:
        fail("CLI 出现禁止的自动执行子命令: %s" % sorted(subcommands & forbidden))
    required = {"observe", "run", "list", "show", "decide", "validate"}
    if not required.issubset(subcommands):
        fail("CLI 缺少必要子命令")

    for source in sorted(expected.glob("*.py")):
        compile(source.read_text(encoding="utf-8"), str(source), "exec")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "tests"),
        "-p",
        "test_v51_controlled_evolution.py",
        "-v",
    ]
    completed = subprocess.run(command, cwd=str(ROOT), env=env, text=True, capture_output=True)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        return completed.returncode

    result = {
        "ok": True,
        "version": "5.1.0",
        "authority": "runtime/cp_runtime/evolution",
        "execution_authorization": "NONE",
        "automatic_execution": False,
        "subcommands": sorted(subcommands),
        "tests": "PASS",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
