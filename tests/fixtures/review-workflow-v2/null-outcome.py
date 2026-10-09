from __future__ import annotations
import re,json,hashlib,hmac,unicodedata
from datetime import datetime,timezone
from pathlib import PurePosixPath
from typing import Any,Mapping,Tuple

TERMINAL_OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}

EVENT_TYPES = {"TURN_OPENED", "PRE_TOOL_GUARD", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"}

class EventContractError(ValueError):
    pass

def _text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default

def _validate_identity_and_terminal(payload: Mapping[str, Any]) -> Tuple[str, str, str]:
    event_type = _text(payload.get("event_type")).upper()
    if event_type not in EVENT_TYPES:
        raise EventContractError("未知 event_type: %s" % event_type)
    repo_fingerprint = _text(payload.get("repo_fingerprint"))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", repo_fingerprint):
        raise EventContractError("repo_fingerprint 非法")
    project_id = _text(payload.get("project_id"))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", project_id):
        raise EventContractError("project_id 非法")
    terminal = _text(payload.get("terminal_outcome"), "UNKNOWN").upper()
    if terminal not in TERMINAL_OUTCOMES:
        raise EventContractError("terminal_outcome 非法")
    return event_type, project_id, repo_fingerprint
