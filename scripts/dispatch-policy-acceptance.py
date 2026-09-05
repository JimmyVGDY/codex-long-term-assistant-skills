#!/usr/bin/env python3
"""中文：验证派发前策略门禁，不记录宿主实际模型信息。

English: Exercise pre-dispatch policy gates without recording host runtime model facts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]

# 中文：这些精确标识仅作为适配器瞬时输入，绝不复制到证据。
# English: These exact identifiers are transient adapter inputs. They are never copied to evidence.
_CASES = (
    ("allow-luna-low", "gpt-5.6-luna", "low", "allow"),
    ("allow-luna-medium", "gpt-5.6-luna", "medium", "allow"),
    ("allow-terra-medium", "gpt-5.6-terra", "medium", "allow"),
    ("allow-terra-high", "gpt-5.6-terra", "high", "allow"),
    ("deny-terra-xhigh", "gpt-5.6-terra", "xhigh", "deny"),
    ("deny-sol-high", "gpt-5.6-sol", "high", "deny"),
    ("deny-terra-max", "gpt-5.6-terra", "max", "deny"),
    ("deny-terra-ultra", "gpt-5.6-terra", "ultra", "deny"),
)


def _case(case_id: str, model: str, effort: str, expected: str) -> Dict[str, object]:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "spawn_agent",
        "session_id": "dispatch-policy",
        "turn_id": "dispatch-policy",
        "task_id": "dispatch-policy",
        "cwd": str(ROOT),
        "tool_input": {"model": model, "reasoning_effort": effort},
    }
    with tempfile.TemporaryDirectory(prefix="cp-v743-dispatch-policy-") as data:
        environment = dict(os.environ, CP_ASSISTANT_DATA=data)
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "cp_hook.py"), "PreToolUse"],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
    denied = False
    if result.stdout.strip():
        try:
            denied = (
                json.loads(result.stdout)
                .get("hookSpecificOutput", {})
                .get("permissionDecision")
                == "deny"
            )
        except ValueError:
            denied = False
    observed = "deny" if denied else "allow"
    return {
        "case_id": case_id,
        "expected": expected,
        "observed": observed,
        "exit_code": result.returncode,
        "pass": result.returncode == 0 and observed == expected,
    }


def evaluate() -> Dict[str, object]:
    rows = [_case(*case) for case in _CASES]
    passed = all(row["pass"] is True for row in rows)
    return {
        "ok": passed,
        "schema_version": "2.0",
        "dispatch_policy_status": "PASS" if passed else "FAIL",
        "automatic_ceiling_profile": "terra-high",
        "case_count": len(rows),
        "cases": rows,
        "privacy": {
            "host_model_information_collected": False,
            "host_model_information_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V7.4.6 dispatch-policy acceptance")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
