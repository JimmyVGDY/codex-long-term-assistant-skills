#!/usr/bin/env python3
"""中文：隔离验证当前 Desktop 默认与冻结旧策略，不调用真实模型。

English: Isolate current Desktop-default and frozen legacy checks without real model calls.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.dispatch_policy import DispatchPolicyError, policy, resolve_request  # noqa: E402
from cp_runtime.g6_flexible_policy import POLICY_ID, PROFILES, profile_spec  # noqa: E402

LEGACY_ID = "reviewer-matrix-v3"
LEGACY = policy(LEGACY_ID)


def observed_permission(output: str) -> str:
    """中文：只有明确中性或许可输出算放行，坏 JSON 不冒充允许。

    English: Only explicit neutral or permit output counts as allow; malformed JSON never does.
    """
    if not output.strip():
        return "allow"
    try:
        value = json.loads(output)
    except (ValueError, TypeError):
        return "invalid-output"
    if value == {}:
        return "allow"
    if not isinstance(value, dict):
        return "invalid-output"
    hook = value.get("hookSpecificOutput")
    if not isinstance(hook, dict) or hook.get("hookEventName") != "PreToolUse":
        return "invalid-output"
    return hook.get("permissionDecision") if hook.get("permissionDecision") in {"allow", "deny"} else "invalid-output"


def current_case(case_id: str, model: str, effort: str, role: str,
                 expected: str, *, direct_choice: bool = True) -> dict[str, Any]:
    """中文：通过真实 Hook 入口消费合成事件，所有状态限定在临时账户。

    English: Exercise the real Hook entry with synthetic events in an isolated temporary account.
    """
    session = "synthetic-" + case_id
    payload = {
        "hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
        "session_id": session, "turn_id": "acceptance-turn", "task_id": session,
        "tool_use_id": "acceptance-call", "cwd": str(ROOT),
        "tool_input": {"task_name": "acceptance_case", "model": model,
                       "reasoning_effort": effort, "agent_type": role,
                       "fork_turns": "none", "message": "Bounded policy fixture; no native model call."},
    }
    with tempfile.TemporaryDirectory(prefix="cp-g6-policy-acceptance-") as temporary:
        environment = dict(os.environ)
        for name in tuple(environment):
            if name.startswith("CP_"):
                environment.pop(name)
        environment.update(CODEX_HOME=str(Path(temporary) / "codex-home"),
                           CP_ASSISTANT_DATA=str(Path(temporary) / "events"),
                           PLUGIN_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        if direct_choice:
            prompt = {"hook_event_name": "UserPromptSubmit", "session_id": session,
                      "turn_id": "acceptance-turn", "cwd": str(ROOT),
                      "prompt": "use " + model + " " + effort}
            prepared = subprocess.run([sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), "UserPromptSubmit"],
                                      input=json.dumps(prompt), text=True, encoding="utf-8",
                                      capture_output=True, env=environment, cwd=ROOT, timeout=30)
            if prepared.returncode:
                return {"case_id": case_id, "expected": expected, "observed": "prompt-error",
                        "exit_code": prepared.returncode, "pass": False}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), "PreToolUse"],
                                input=json.dumps(payload), text=True, encoding="utf-8",
                                capture_output=True, env=environment, cwd=ROOT, timeout=30)
    observed = observed_permission(result.stdout)
    return {"case_id": case_id, "expected": expected, "observed": observed,
            "exit_code": result.returncode,
            "pass": result.returncode == 0 and observed == expected}


def legacy_case(case_id: str, model: str, effort: str, role: str, expected: str) -> dict[str, Any]:
    """中文：显式核验冻结 V3 的型号和角色，不借用当前默认 Hook。

    English: Check frozen V3 tuples and roles explicitly, without repurposing the current-default Hook.
    """
    try:
        if not model or not effort:
            raise DispatchPolicyError("EXPLICIT_SUBAGENT_TUPLE_REQUIRED")
        resolve_request(model, effort, "luna-low", role, LEGACY_ID)
        observed = "allow"
    except DispatchPolicyError:
        observed = "deny"
    return {"case_id": case_id, "expected": expected, "observed": observed,
            "pass": observed == expected}


def evaluate() -> dict[str, Any]:
    current = []
    for role in ("cp_review_data_contract", "worker", "explorer"):
        for name in PROFILES:
            spec = profile_spec(name)
            current.append(current_case(role + "-" + name, spec["model"], spec["effort"], role, "allow"))
    current.append(current_case("missing-evidence-default", "gpt-6-sol", "medium", "worker", "allow", direct_choice=False))
    negative = [("deny-" + effort, "gpt-6-astra", effort, "cp_review_data_contract", "deny")
                for effort in ("xhigh", "max", "ultra")]
    negative += [("deny-unknown-role", "gpt-6-sol", "medium", "cp_review_spoof", "deny"),
                 ("deny-implicit-review", "", "", "cp_review_data_contract", "deny"),
                 ("deny-unknown-model", "unknown", "low", "cp_review_data_contract", "deny"),
                 ("deny-legacy-default", "gpt-5.6-luna", "low", "worker", "deny")]
    current.extend(current_case(*case, direct_choice=False) for case in negative)
    legacy = []
    for role in ("cp_review_data_contract", "worker", "explorer"):
        role_name = "reviewer" if role.startswith("cp_review_") else role
        for name, spec in LEGACY["profiles"].items():
            expected = "allow" if name in LEGACY["role_profiles"][role_name] else "deny"
            legacy.append(legacy_case(role_name + "-" + name, spec["model"], spec["effort"], role, expected))
    legacy.extend(legacy_case(*case) for case in negative if case[0] != "deny-legacy-default")
    passed = all(row["pass"] for row in current + legacy)
    return {"ok": passed, "schema_version": "4.0", "policy_id": POLICY_ID,
            "evidence_scope": "synthetic-policy-only", "native_model_calls": 0,
            "dispatch_policy_status": "PASS" if passed else "FAIL",
            "automatic_ceiling_profile": "g6-astra-high",
            "registered_reviewer_ceiling_profile": "g6-astra-high",
            "current_case_count": len(current), "legacy_case_count": len(legacy),
            "case_count": len(current) + len(legacy), "cases": current,
            "legacy_policy_id": LEGACY_ID, "legacy_cases": legacy,
            "legacy_evidence_scope": "frozen-tuple-admission-only; lifecycle replay tested separately",
            "test_state_isolation": "temporary CODEX_HOME and CP_ASSISTANT_DATA",
            "privacy": {"host_model_information_collected": False,
                        "host_model_information_exported": False}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Desktop current and frozen dispatch-policy acceptance")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
