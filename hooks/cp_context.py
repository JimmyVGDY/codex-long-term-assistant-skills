#!/usr/bin/env python3
"""中文：按真实根归属约束子任务；English: identity-first local-tool guard, no prompt telemetry."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from cp_runtime.routing_contract import _object, _constant
from cp_runtime.g6_handoff_v1 import route as g6_route
from cp_runtime.routing_hook_v5 import registered_path, child_tool

def main():
    raw = sys.stdin.buffer.read(2_097_153)
    if len(raw) > 2_097_152:
        raise ValueError("V5_HOOK_SIZE")
    data = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(data, dict):
        raise ValueError("V5_HOOK_OBJECT")
    owner = g6_route(data)
    if owner is not None and owner[0] == "new":
        # 中文：G6 子任务绑定自身账本，没有 V5 上下文读取许可；旧归属和未绑定调用仍使用原 V5 门禁。
        # English: The G6 child is bound to its own ledger and has no V5 context-reader
        # permit.  V5 keeps its original guard for old-owner and unbound calls.
        print("{}")
        return
    path = registered_path(data)
    if path and data.get("agent_id"):
        result = child_tool(path, data)
        print(json.dumps(result, ensure_ascii=True))
    else:
        print("{}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        event = sys.argv[1] if len(sys.argv) == 2 else "PreToolUse"
        code = str(exc) if str(exc).startswith(("V5_", "CONTEXT_V2_")) else "V5_CONTEXT_GUARD_FAILED"
        if event == "PreToolUse":
            result = {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                      "permissionDecisionReason": code}}
        else:
            result = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                      "additionalContext": "Context delivery was not verified. Return incomplete."}}
        print(json.dumps(result, ensure_ascii=True))
