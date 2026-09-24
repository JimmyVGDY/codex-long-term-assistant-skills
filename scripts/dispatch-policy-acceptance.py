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
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.dispatch_policy import policy  # noqa: E402

# 中文：这些精确标识仅作为适配器瞬时输入，绝不复制到证据。
# English: These exact identifiers are transient adapter inputs. They are never copied to evidence.
_POLICY = policy()
_CASES = [
    ("reviewer-" + name, spec["model"], spec["effort"], "cp_review_data_contract", "allow")
    for name, spec in _POLICY["profiles"].items()
] + [
    (role + "-" + name, spec["model"], spec["effort"], role,
     "allow" if name in _POLICY["role_profiles"][role] else "deny")
    for role in ("worker", "explorer") for name, spec in _POLICY["profiles"].items()
] + [("deny-" + effort, "gpt-6-astra", effort, "cp_review_data_contract", "deny")
     for effort in ("xhigh", "max", "ultra")] + [
    ("deny-unknown-role", "gpt-5.6-sol", "low", "cp_review_spoof", "deny"),
    ("deny-implicit-review", "", "", "cp_review_data_contract", "deny"),
    ("deny-unknown-model", "unknown", "low", "cp_review_data_contract", "deny"),
]


def _case(case_id: str, model: str, effort: str, role: str, expected: str) -> Dict[str, object]:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "spawn_agent",
        "session_id": "dispatch-policy",
        "turn_id": "dispatch-policy",
        "task_id": "dispatch-policy",
        "cwd": str(ROOT),
        "tool_input": {"model": model, "reasoning_effort": effort, "agent_type": role},
    }
    with tempfile.TemporaryDirectory(prefix="cp-v743-dispatch-policy-") as data:
        environment = dict(os.environ, CP_ASSISTANT_DATA=data, CP_DELEGATION_BUDGET_PATH="",
                           CP_DELEGATION_BUDGET_REQUIRED="0", PYTHONDONTWRITEBYTECODE="1")
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
        "schema_version": "3.0",
        "evidence_scope": "synthetic-policy-only",
        "dispatch_policy_status": "PASS" if passed else "FAIL",
        "automatic_ceiling_profile": "terra-high",
        "registered_reviewer_ceiling_profile": "astra-high",
        "selection_scoring": "tested separately; this report exercises role/tuple admission only",
        "case_count": len(rows),
        "cases": rows,
        "privacy": {
            "host_model_information_collected": False,
            "host_model_information_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V7.13.3 dispatch-policy acceptance")
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
