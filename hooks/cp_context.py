#!/usr/bin/env python3
"""中文：仅约束登记的 V5 子任务；English: identity-first local-tool guard, no prompt telemetry."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from cp_runtime.routing_contract import _object, _constant
from cp_runtime.routing_hook_v5 import registered_path, child_tool

def main():
    raw = sys.stdin.buffer.read(2_097_153)
    if len(raw) > 2_097_152:
        raise ValueError("V5_HOOK_SIZE")
    data = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(data, dict):
        raise ValueError("V5_HOOK_OBJECT")
    path = registered_path(data)
    if path and data.get("agent_id"):
        child_tool(path, data)
    print("{}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        event = sys.argv[1] if len(sys.argv) == 2 else "PreToolUse"
        code = str(exc) if str(exc).startswith("V5_") else "V5_CONTEXT_GUARD_FAILED"
        if event == "PreToolUse":
            result = {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                      "permissionDecisionReason": code}}
        else:
            result = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                      "additionalContext": "Context delivery was not verified. Return incomplete."}}
        print(json.dumps(result, ensure_ascii=True))
