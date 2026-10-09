from __future__ import annotations
import re,json,hashlib,hmac,unicodedata
from datetime import datetime,timezone
from pathlib import PurePosixPath
from typing import Any,Mapping,Tuple

class RuntimeContractError(RuntimeError):
    """中文：失败关闭的 Runtime 契约异常。

    English: A fail-closed runtime contract violation.
    """

def parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise RuntimeContractError("时间必须包含时区")
    return parsed.astimezone(timezone.utc)

class RoutingError(ValueError):
    """中文：固定原因码；English: errors contain no raw input or source content."""

def fail(code: str) -> None:
    raise RoutingError(code)

def assert_current_window(value: Mapping[str, Any], now: str) -> None:
    try:
        current, start, end = map(parse_iso, (now, value["created_at"], value["expires_at"]))
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        raise RoutingError("TIME_WINDOW_INVALID") from exc
    if not start <= current < end:
        fail("SNAPSHOT_EXPIRED_OR_NOT_YET_VALID")
