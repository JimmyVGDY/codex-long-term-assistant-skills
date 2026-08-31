#!/usr/bin/env python3
"""Codex V6 生命周期 Hook：模型上限防护 + 本地最小元数据观测。"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

# Codex writes hook payloads as UTF-8. Windows native Python otherwise decodes
# redirected stdin with the active ANSI code page (for example GBK), which
# breaks Stop payloads containing a Chinese last_assistant_message.
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")

ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import append_event, project_id_for, stable_repo_fingerprint  # noqa: E402

ALLOWED_REASONING = {"", "none", "minimal", "low", "medium", "high"}
ALLOWED_AUTOMATIC_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra"}
DENY_MARKERS = ("sol", "gpt-5.6-sol", "xhigh", "extra-high", "extra_high", "ultra", "max")


def _read() -> Dict[str, Any]:
    raw = b""
    try:
        # Let json.loads inspect the raw byte stream (including an optional
        # UTF BOM) instead of depending on Windows' redirected-text encoding.
        raw = sys.stdin.buffer.read()
        data = json.loads(raw) if raw.strip() else {}
        return data
    except Exception:
        # Codex CLI 0.150.1 on native Windows can truncate a non-ASCII
        # last_assistant_message while constructing Stop stdin. All lifecycle
        # identity fields precede that final free-text field, so discard only
        # the damaged suffix and recover the valid JSON object prefix.
        damaged = re.search(rb',\s*"last_assistant_message"\s*:', raw)
        if damaged is not None:
            try:
                recovered = json.loads(raw[: damaged.start()] + b"}")
                if isinstance(recovered, dict):
                    return recovered
            except Exception:
                pass
        # Last-resort event-name recovery keeps Stop stdout valid without
        # persisting any prompt or assistant content.
        hook = re.search(rb'"hook_event_name"\s*:\s*"([A-Za-z]+)"', raw)
        if hook is not None:
            return {"hook_event_name": hook.group(1).decode("ascii")}
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
    elif model and model not in ALLOWED_AUTOMATIC_MODELS:
        reason = "显式模型无法证明不超过 Terra High，按 fail-closed 策略拒绝；请使用 gpt-5.6-luna、gpt-5.6-terra 或省略显式模型。"
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
        configured = os.environ.get("CODEX_HOME")
        if configured and os.name == "nt":
            match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", configured.strip().replace("\\", "/"))
            if match:
                drive = match.group(1).upper()
                rest = (match.group(2) or "").replace("/", "\\")
                configured = drive + ":\\" + rest if rest else drive + ":\\"
        codex_home = Path(configured) if configured else (Path.home() / ".codex")
        root = codex_home / "project-context" / event["project_id"]
    return root / "feedback" / "task-outcome-v2.jsonl"


def _sandbox_fallback_path(event: Mapping[str, Any]) -> Path:
    """Return a repo-external path that Codex workspace-write sandboxes permit.

    Native Windows Codex currently permits the process temporary directory but
    can deny a Hook's write to the user-level CODEX_HOME. The fallback is used
    only for that permission failure; integrity/schema errors still fail closed
    inside append_event and are never redirected to a fresh chain.
    """
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    return (
        temp_root
        / "codex-cp-assistant-v6"
        / "project-context"
        / str(event["project_id"])
        / "feedback"
        / "task-outcome-v2.jsonl"
    )


def main() -> int:
    data = _read()
    expected_hook = sys.argv[1] if len(sys.argv) > 1 else ""
    allowed_hooks = {"UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop", "Stop", "SessionEnd"}
    if expected_hook not in allowed_hooks:
        expected_hook = ""
    hook_name = str(_lookup(data, "hook_event_name", "hookEventName", "event_name", "event") or expected_hook)
    if hook_name and "hook_event_name" not in data:
        data["hook_event_name"] = hook_name
    if expected_hook == "PreToolUse" and not str(_lookup(data, "tool_name", "tool") or ""):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "PreToolUse 输入无法解析，按 fail-closed 策略拒绝自动子 Agent。"}}, ensure_ascii=False))
        return 0
    guard = _guard(data)
    if guard is not None:
        print(json.dumps(guard, ensure_ascii=False))
        return 0
    try:
        event = _event(data)
    except Exception:
        # Observation metadata can be incomplete or malformed on some native
        # Windows host paths. Never let event construction prevent Stop from
        # returning its valid neutral response. The PreToolUse model guard has
        # already run above and remains fail-closed.
        event = None
    if event is not None:
        try:
            event_path = _data_path(event)
            append_event(event_path, event, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
        except PermissionError:
            try:
                append_event(_sandbox_fallback_path(event), event, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
            except Exception:
                # 观察失败不打断开发任务；模型上限拦截在前面单独 fail-closed。
                pass
        except Exception:
            # 数据损坏或哈希链错误不得通过创建新链绕过。
            pass
    # Normal Stop handling returns the neutral response documented by the host.
    # The recovery above is what ensures this branch still runs when Windows
    # truncates a non-ASCII last_assistant_message payload.
    if hook_name == "Stop":
        print("{}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Lifecycle observation is fail-open, but an unexpected PreToolUse
        # failure must never turn into an implicit model-policy allow.
        expected = sys.argv[1] if len(sys.argv) > 1 else ""
        if expected == "PreToolUse":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "PreToolUse Hook 异常，按 fail-closed 策略拒绝自动子 Agent。"}}, ensure_ascii=False))
        elif expected == "Stop":
            print("{}")
        raise SystemExit(0)
