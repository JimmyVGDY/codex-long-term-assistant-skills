#!/usr/bin/env python3
"""Exercise the installed automatic subagent request ceiling."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _case(model: str, effort: str) -> dict:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
               "session_id": "model-gate", "turn_id": "model-gate", "task_id": "model-gate",
               "cwd": str(ROOT), "tool_input": {"model": model, "reasoning_effort": effort}}
    with tempfile.TemporaryDirectory(prefix="cp-v66-model-gate-") as data:
        environment = dict(os.environ, CP_ASSISTANT_DATA=data)
        result = subprocess.run([sys.executable, str(ROOT / "hooks" / "cp_hook.py"), "PreToolUse"],
                                input=json.dumps(payload), text=True, encoding="utf-8",
                                capture_output=True, env=environment, timeout=10, check=False)
    denied = False
    if result.stdout.strip():
        try:
            denied = json.loads(result.stdout).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
        except ValueError:
            denied = False
    return {"model": model, "reasoning_effort": effort, "denied": denied,
            "exit_code": result.returncode}


def evaluate() -> dict:
    allow = [_case("gpt-5.6-luna", "low"), _case("gpt-5.6-luna", "medium"),
             _case("gpt-5.6-terra", "medium"), _case("gpt-5.6-terra", "high")]
    deny = [_case("gpt-5.6-terra", "xhigh"), _case("gpt-5.6-sol", "high"),
            _case("gpt-5.6-terra", "max"), _case("gpt-5.6-terra", "ultra")]
    passed = all(not item["denied"] and item["exit_code"] == 0 for item in allow)
    passed = passed and all(item["denied"] and item["exit_code"] == 0 for item in deny)
    return {"ok": passed, "schema_version": "1.0",
            "requested_model_policy": "PASS" if passed else "FAIL",
            "automatic_ceiling": "gpt-5.6-terra / high", "allow_cases": allow, "deny_cases": deny,
            "runtime_model_evidence": "NOT_EVALUATED"}


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 requested-model policy acceptance")
    parser.add_argument("--output")
    args = parser.parse_args(); report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
