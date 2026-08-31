#!/usr/bin/env python3
"""Codex V6 生命周期 Hook：模型上限防护 + 本地最小元数据观测。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import append_event, project_id_for, stable_repo_fingerprint  # noqa: E402

ALLOWED_REASONING = {"", "none", "minimal", "low", "medium", "high"}
DENY_MARKERS = ("sol", "gpt-5.6-sol", "xhigh", "extra-high", "extra_high", "ultra", "max")


def _read() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _lookup(data: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data.get(name) is not None:
            return data.get(name)
    return None


def _tool_input(data: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = _lookup(data, "tool_input", "input", "arguments")
    return candidate if isinstance(candidate, Mapping) else {}


def _guard(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    tool = str(_lookup(data, "tool_name", "tool") or "").lower()
    if tool not in {"agent", "spawn_agent"}:
        return None
    args = _tool_input(data)
    model = str(_lookup(args, "model", "model_name") or "").strip().lower()
    effort = str(_lookup(args, "reasoning_effort", "reasoning", "effort") or "").strip().lower()
    reason = ""
    if any(marker in model for marker in DENY_MARKERS):
        reason = "自动子 Agent 模型不得超过 Terra High；显式 Sol/更高模型被 V6 Policy 拒绝。"
    elif effort not in ALLOWED_REASONING:
        reason = "自动子 Agent reasoning_effort 最高为 high。"
    elif model and not ("terra" in model or "luna" in model):
        reason = "显式模型无法证明不超过 Terra High，按 fail-closed 策略拒绝；请使用 Luna/Terra 或省略显式模型。"
    if not reason:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}


def _event(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    hook = str(_lookup(data, "hook_event_name", "hookEventName", "event_name", "event") or "")
    event_map = {
        "UserPromptSubmit": "TURN_OPENED",
        "PreToolUse": "PRE_TOOL_GUARD",
        "SubagentStart": "SUBAGENT_STARTED",
        "SubagentStop": "SUBAGENT_STOPPED",
        "Stop": "TASK_COMPLETED",
        "SessionEnd": "SESSION_ENDED",
    }
    event_type = event_map.get(hook)
    if not event_type:
        return None
    cwd = str(_lookup(data, "cwd", "working_directory") or os.getcwd())
    fingerprint = stable_repo_fingerprint(cwd)
    session_id = str(_lookup(data, "session_id", "sessionId", "thread_id") or "")
    turn_id = str(_lookup(data, "turn_id", "turnId") or "")
    task_id = str(_lookup(data, "task_id", "taskId") or turn_id or session_id)
    model = str(_lookup(data, "model", "actual_model") or "")
    effort = str(_lookup(data, "reasoning_effort", "actual_reasoning_effort") or "")
    terminal = str(_lookup(data, "terminal_outcome", "quality_outcome") or "UNKNOWN") if event_type == "TASK_COMPLETED" else "UNKNOWN"
    metadata: Dict[str, Any] = {}
    for key in ("agent_id", "agent_type", "permission_mode", "tool_name", "stop_hook_active"):
        value = data.get(key)
        if value is not None:
            metadata[key] = value
    return {
        "event_type": event_type,
        "session_id": session_id,
        "turn_id": turn_id,
        "task_id": task_id,
        "project_id": project_id_for(fingerprint, cwd),
        "repo_fingerprint": fingerprint,
        "terminal_outcome": terminal,
        "actual_model": model,
        "actual_reasoning_effort": effort,
        "metadata": metadata,
    }


def _data_path(event: Mapping[str, Any]) -> Path:
    base = os.environ.get("CP_ASSISTANT_DATA")
    if base:
        root = Path(base).expanduser() / event["project_id"]
    else:
        codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        root = codex_home / "project-context" / event["project_id"]
    return root / "feedback" / "task-outcome-v2.jsonl"


def main() -> int:
    data = _read()
    guard = _guard(data)
    if guard is not None:
        print(json.dumps(guard, ensure_ascii=False))
        return 0
    event = _event(data)
    if event is not None:
        try:
            append_event(_data_path(event), event, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
        except Exception as exc:
            # 观察失败默认不打断开发任务；模型上限拦截在前面单独 fail-closed。
            print(json.dumps({"systemMessage": "V6 观察事件写入失败：%s" % type(exc).__name__}, ensure_ascii=False))
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
