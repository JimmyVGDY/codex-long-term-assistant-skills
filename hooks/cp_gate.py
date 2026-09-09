#!/usr/bin/env python3
"""中文：受父进程超时保护的门禁及旧观察顺序合并；只接收最小元数据。

English: Parent-supervised gate and legacy observation ordering; receives minimal metadata only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.capability_gate_hook import WIRE_LIMIT, failure_response, handle
from cp_runtime.capability_store import CapabilityError, require, unique_json_object
import cp_hook as observer


def main() -> int:
    event = "Stop"
    try:
        raw = sys.stdin.buffer.read(WIRE_LIMIT + 1)
        require(len(raw) <= WIRE_LIMIT, "GATE_INPUT_LIMIT")
        data = json.loads(raw, object_pairs_hook=unique_json_object)
        require(isinstance(data, dict), "GATE_HOST_IDENTITY")
        event = data.get("hook_event_name", "Stop")
        result = handle(ROOT, data)
        response = result["response"]
        observation = None
        if result["observe"] and event not in {"PreToolUse", "Interrupt"}:
            observation = observer._observe(data, allow_feedback=result["allow_feedback"])
        if event == "UserPromptSubmit":
            feedback = observer._feedback_context(observation)
            if feedback:
                specific = response.setdefault("hookSpecificOutput", {"hookEventName": event})
                specific["additionalContext"] = (specific.get("additionalContext", "") + "\n" + feedback).strip()
    except CapabilityError as exc:
        response = failure_response(event, str(exc))
    except Exception:
        response = failure_response(event, "GATE_WORKER_FAILED")
    output = json.dumps(response, ensure_ascii=True)
    if len(output.encode("utf-8")) > WIRE_LIMIT:
        output = json.dumps(failure_response(event, "GATE_OUTPUT_LIMIT"), ensure_ascii=True)
    print(output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
