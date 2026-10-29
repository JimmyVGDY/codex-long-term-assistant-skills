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


def transcript_path(path: Path) -> Path:
    """中文：只展开已核验账户根别名，内部链接仍按原合同拒绝。
    English: Expand only a verified account-root alias; retain strict inner-link checks.
    """
    from .common import resolve_codex_home
    from .routing_context_contract import safe_file
    from .routing_contract import fail
    if not path.is_absolute() or ".." in path.parts:
        return safe_file(path)
    home = resolve_codex_home()
    roots = (Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().absolute(),
             (Path.home() / ".codex").absolute())
    for root in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0] != "sessions" or not root.samefile(home):
            fail("TASK_NATIVE_HOME_IDENTITY")
        canonical = safe_file(home / relative)
        if not path.samefile(canonical):
            fail("TASK_NATIVE_HOME_IDENTITY")
        return canonical
    return safe_file(path)


def session_header(path: Path, *, session_id: str) -> tuple[dict, dict]:
    """中文：会话身份独立核验；目录与授权约束仍由调用方执行。
    English: Verify a parent session independently of its initial workspace.

    Workspace/authority checks remain the responsibility of the caller.
    """
    from .common import resolve_codex_home
    from .context_final_v2 import read_bound_transcript
    from .routing_context_contract import safe_file
    from .path_identity import path_is_within
    from .routing_contract import fail
    path = safe_file(path)
    if (not path_is_within(path, resolve_codex_home() / "sessions")
            or not path.name.endswith(session_id + ".jsonl")):
        fail("G6_ALLOWANCE_NATIVE_SOURCE_PATH")
    raw, binding = read_bound_transcript(path, header_only=True)
    header = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    meta = header.get("payload", {}) if isinstance(header, dict) else None
    if (not isinstance(header, dict) or not isinstance(meta, dict)
            or header.get("type") != "session_meta" or meta.get("id") != session_id
            or not isinstance(meta.get("cwd"), str)
            or isinstance(meta.get("source"), dict) and "subagent" in meta["source"]):
        fail("G6_ALLOWANCE_NATIVE_SOURCE_IDENTITY")
    return header, binding


def complete_window(path: Path, *, maximum: int = 2_000_000, before_byte: int | None = None) -> tuple[bytes, dict[str, Any]]:
    """中文：调用者先验证宿主路径和身份；只舍弃边界处不完整的行。

    English: Callers verify native path/identity first. Discard incomplete
    boundary lines only, retaining a complete final even during a later append.
    """
    if type(maximum) is not int or not 1024 <= maximum <= 2_000_000:
        raise ValueError("NATIVE_WINDOW_LIMIT")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before_byte is not None and (type(before_byte) is not int or not 0 < before_byte <= before.st_size):
            raise ValueError("NATIVE_WINDOW_END")
        stop = before.st_size if before_byte is None else before_byte
        start = max(0, stop - maximum)
        scan_start = start
        stream.seek(start)
        raw = stream.read(stop - start)
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
                 "partial_tail": end < stop, "truncated_prefix": start > 0,
                 "scan_start": scan_start, "scan_end": stop}


def complete_tail(path: Path, *, maximum: int = 2_000_000) -> tuple[bytes, dict[str, Any]]:
    """中文：保留旧回执窗口字段与默认末尾读取语义。
    English: Preserve the legacy receipt fields and tail-reading semantics.
    """
    raw, window = complete_window(path, maximum=maximum)
    window.pop("scan_start")
    window.pop("scan_end")
    return raw, window


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
