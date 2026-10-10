"""中文：原生回执的有界完整行窗口，不保存对话正文。

English: Bounded complete-line windows for native receipts, without body storage.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .common import parse_iso
from .routing_contract import _object, _constant


def complete_tail(path: Path, *, maximum: int = 2_000_000) -> tuple[bytes, dict[str, Any]]:
    """中文：调用者先验证宿主路径和身份；只舍弃边界处不完整的行。

    English: Callers verify native path/identity first. Discard incomplete
    boundary lines only, retaining a complete final even during a later append.
    """
    if type(maximum) is not int or not 1024 <= maximum <= 2_000_000:
        raise ValueError("NATIVE_WINDOW_LIMIT")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        start = max(0, before.st_size - maximum)
        stream.seek(start)
        raw = stream.read(maximum)
        after = os.fstat(stream.fileno())
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or after.st_size < before.st_size:
        raise ValueError("NATIVE_WINDOW_CHANGED")
    if start:
        boundary = raw.find(b"\n")
        dropped = len(raw) if boundary < 0 else boundary + 1
        raw, start = raw[dropped:], start + dropped
    end = start + len(raw)
    if raw and not raw.endswith(b"\n"):
        last = raw.rfind(b"\n")
        raw = raw[:last + 1] if last >= 0 else b""
        end = start + len(raw)
    return raw, {"source": "native-transcript-window", "start": start, "end": end,
                 "observed_size": before.st_size, "sha256": hashlib.sha256(raw).hexdigest(),
                 "partial_tail": end < before.st_size, "truncated_prefix": start > 0}


def turn_evidence(path: Path, turn_id: str, not_before: str) -> dict[str, Any] | None:
    """中文：只有当前原生回合且不早于预占的事件才能证明续跑已发生。

    English: Only this native turn, no earlier than its reservation, can prove
    that a continuation actually started.
    """
    raw, window = complete_tail(path)
    for line in raw.splitlines():
        value = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
        payload = value.get("payload", {})
        stamp = value.get("timestamp")
        if (value.get("type") == "event_msg" and payload.get("turn_id") == turn_id
                and payload.get("type") in {"task_started", "task_complete", "turn_complete", "turn_aborted"}
                and isinstance(stamp, str) and parse_iso(stamp) >= parse_iso(not_before)):
            return {"window": window, "turn_id": turn_id, "event_type": payload["type"], "timestamp": stamp}
    return None
